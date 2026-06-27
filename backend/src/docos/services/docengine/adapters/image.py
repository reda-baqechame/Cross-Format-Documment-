"""Image adapter (Pillow + optional Tesseract OCR).

Builds a single page holding the image, then — when a Tesseract engine with language
data is available — runs OCR to recover text into paragraphs/runs so a scan becomes
searchable, editable, and exportable. OCR is best-effort and engine-agnostic: it tries
``tesserocr`` (bundled libtesseract, no external binary) first, then the ``pytesseract``
CLI wrapper. Without either — or without language data — the image is still ingested,
just without recovered text.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from PIL import Image

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ImageNode, PageNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "TIFF": "image/tiff"}


def ocr_available() -> bool:
    """True if some Tesseract engine *with language data* can run."""
    try:
        import tesserocr

        if tesserocr.get_languages()[1]:
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return bool(pytesseract.get_languages())
    except Exception:  # noqa: BLE001
        return False


def _ocr_text(image: Image.Image) -> str | None:
    """OCR via the bundled ``tesserocr`` first, then the ``pytesseract`` CLI wrapper."""
    try:
        import tesserocr

        if tesserocr.get_languages()[1]:  # language data present
            return tesserocr.image_to_text(image)
    except Exception:  # noqa: BLE001 - fall through to the next engine
        pass
    try:
        import pytesseract

        pytesseract.get_tesseract_version()  # raises if the binary is missing
        return pytesseract.image_to_string(image)
    except Exception:  # noqa: BLE001 - OCR is best-effort, never fatal to ingest
        return None


class ImageAdapter(FormatAdapter):
    format_id = "image"
    supported_mimes = ("image/png", "image/jpeg", "image/tiff")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        mime = _MIME_BY_FORMAT.get(image.format or "", "image/png")
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="image",
                source_mime=mime,
                created_at=now,
                modified_at=now,
                page_count=1,
            ),
        )
        doc.add_node(root)

        page = PageNode(
            id=new_node_id("page"),
            parent_id=root.id,
            page_number=1,
            width=float(width),
            height=float(height),
            reading_order=0,
        )
        root.children.append(page.id)
        doc.add_node(page)

        img_node = ImageNode(
            id=new_node_id("img"),
            parent_id=page.id,
            blob_ref="original",  # the uploaded bytes are the image itself
            mime=mime,
            attrs={"persisted": True, "width": width, "height": height},
        )
        page.children.append(img_node.id)
        doc.add_node(img_node)

        self._ocr_into(doc, page, image, data)
        return doc

    def _ocr_into(
        self, doc: CanonicalDocument, page: PageNode, image: Image.Image, data: bytes
    ) -> None:
        """Recover text via Tesseract when available.

        Prefers a confident scanned-grid table, then *structured* recognition (positioned,
        confidence-scored word runs); falls back to flat text; a no-op when no engine is present.
        """
        if self._tables_into(doc, page, data):
            return
        if self._structured_ocr_into(doc, page, data):
            return

        text = _ocr_text(image)
        if not text:
            return

        order = 1
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            para = ParagraphNode(id=new_node_id(), parent_id=page.id, reading_order=order)
            run = RunNode(id=new_node_id(), parent_id=para.id, text=block)
            para.children.append(run.id)
            page.children.append(para.id)
            doc.add_node(para)
            doc.add_node(run)
            order += 1
        if order > 1:
            doc.accessibility.tagged = True

    def _tables_into(self, doc: CanonicalDocument, page: PageNode, data: bytes) -> bool:
        """Attach a conservatively-detected scanned-grid table. True if one was emitted."""
        try:
            from docos.model.nodes import TableNode
            from docos.services.ocr.tesseract import build_table_nodes

            nodes = build_table_nodes(data, parent_id=page.id)
        except Exception:  # noqa: BLE001 - table detection is best-effort; caller falls back
            return False
        if not nodes:
            return False
        for node in nodes:
            doc.add_node(node)
            if isinstance(node, TableNode):
                page.children.append(node.id)
        doc.accessibility.tagged = True
        return True

    def _structured_ocr_into(self, doc: CanonicalDocument, page: PageNode, data: bytes) -> bool:
        """Attach positioned, confidence-tagged word runs. True if anything was recognised.

        Uses the OCR engine selected in settings (Tesseract by default, PaddleOCR when configured
        and installed); both implement the same ``OcrStructureService`` interface.
        """
        try:
            from docos.services.ocr.factory import get_ocr_service

            ocr = get_ocr_service()
            runs = ocr.recognize(data)
            if not runs:
                return False
            order = {nid: i for i, nid in enumerate(ocr.infer_reading_order(runs))}
            runs.sort(key=lambda r: order.get(r.id, 0))
        except Exception:  # noqa: BLE001 - structured OCR is best-effort; caller falls back
            return False

        para = ParagraphNode(id=new_node_id(), parent_id=page.id, reading_order=1)
        for run in runs:
            run.parent_id = para.id
            run.text = f"{run.text} "  # keep words separated for export/search
            para.children.append(run.id)
            doc.add_node(run)
        page.children.append(para.id)
        doc.add_node(para)
        doc.accessibility.tagged = True
        return True

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("ImageAdapter.render_preview — original bytes serve as preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        from docos.services.docengine.writers.image_writer import model_to_png

        return model_to_png(doc)
