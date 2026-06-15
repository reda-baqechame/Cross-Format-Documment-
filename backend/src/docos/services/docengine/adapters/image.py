"""Image adapter (Pillow + optional Tesseract OCR).

Builds a single page holding the image, then — when a Tesseract binary is available —
runs OCR to recover text into paragraphs/runs so a scan becomes searchable, editable,
and exportable. OCR is best-effort: without Tesseract the image is still ingested,
just without recovered text.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from PIL import Image

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ImageNode, PageNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "TIFF": "image/tiff"}


class ImageAdapter(FormatAdapter):
    format_id = "image"
    supported_mimes = ("image/png", "image/jpeg", "image/tiff")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        mime = _MIME_BY_FORMAT.get(image.format or "", "image/png")
        now = datetime.now(timezone.utc)
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

        self._ocr_into(doc, page, image)
        return doc

    def _ocr_into(self, doc: CanonicalDocument, page: PageNode, image: Image.Image) -> None:
        """Recover text via Tesseract when available; a no-op otherwise."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()  # raises if the binary is missing
            text = pytesseract.image_to_string(image)
        except Exception:  # noqa: BLE001 - OCR is best-effort, never fatal to ingest
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

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("ImageAdapter.render_preview — original bytes serve as preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("ImageAdapter.export — download as DOCX/TXT from the model")
