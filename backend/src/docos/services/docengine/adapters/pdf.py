"""PDF adapter (PyMuPDF) — a functional cross-format adapter.

Extracts the page tree, text blocks (→ paragraphs) and their spans (→ runs with
bbox + basic formatting), images (as :class:`ImageNode` placeholders routed to the
OCR/blob layer), and document metadata. Encryption/permission state is surfaced so
the trust panel can reflect it. ``render_preview`` rasterises a page via
``get_pixmap``; ``export`` (write-back via incremental save) remains a deferred
extension point because faithful PDF mutation is a large effort of its own.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import fitz  # PyMuPDF

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.geometry import BBox
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ImageNode, PageNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

# PyMuPDF span flag bits (see ``TEXT_FONT_*``): italic = 2**1, bold = 2**4.
_FLAG_ITALIC = 1 << 1
_FLAG_BOLD = 1 << 4


class PdfAdapter(FormatAdapter):
    format_id = "pdf"
    supported_mimes = ("application/pdf",)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        pdf = fitz.open(stream=data, filetype="pdf")
        try:
            now = datetime.now(UTC)
            root = RootNode(id=new_node_id("root"))

            raw_meta = dict(pdf.metadata or {})
            meta = DocumentMeta(
                title=raw_meta.get("title") or None,
                author=raw_meta.get("author") or None,
                source_format="pdf",
                source_mime="application/pdf",
                created_at=now,
                modified_at=now,
                page_count=pdf.page_count,
                # Embedded metadata is preserved so the trust layer can inspect/sanitize it.
                custom={k: v for k, v in raw_meta.items() if v},
            )

            doc = CanonicalDocument(doc_id=new_doc_id(), root_id=root.id, meta=meta)
            doc.add_node(root)

            doc.permissions.encrypted = bool(pdf.is_encrypted)
            doc.permissions.password_protected = bool(pdf.needs_pass)

            order = 0
            for pno in range(pdf.page_count):
                page = pdf[pno]
                pnode = PageNode(
                    id=new_node_id("page"),
                    parent_id=root.id,
                    page_number=pno + 1,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    rotation=int(page.rotation or 0),
                    reading_order=order,
                )
                order += 1
                root.children.append(pnode.id)
                doc.add_node(pnode)

                text_dict = page.get_text("dict")
                block_order = 0
                for block in text_dict.get("blocks", []):
                    if block.get("type") == 1:  # image block
                        self._add_image(doc, pnode, block, block_order)
                        block_order += 1
                        continue
                    self._add_text_block(doc, pnode, block, block_order)
                    block_order += 1

            if meta.title:
                doc.accessibility.has_doc_title = True
            return doc
        finally:
            pdf.close()

    def _add_text_block(
        self, doc: CanonicalDocument, page: PageNode, block: dict, order: int
    ) -> None:
        para = ParagraphNode(
            id=new_node_id(),
            parent_id=page.id,
            reading_order=order,
            bbox=_bbox(block.get("bbox")),
        )
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                flags = int(span.get("flags", 0))
                run = RunNode(
                    id=new_node_id(),
                    parent_id=para.id,
                    text=text,
                    bold=bool(flags & _FLAG_BOLD),
                    italic=bool(flags & _FLAG_ITALIC),
                    font=span.get("font") or None,
                    size=float(span["size"]) if span.get("size") else None,
                    color=_color(span.get("color")),
                    bbox=_bbox(span.get("bbox")),
                )
                para.children.append(run.id)
                doc.add_node(run)
        # Skip empty blocks (e.g. whitespace-only) to keep the graph clean.
        if not para.children:
            return
        page.children.append(para.id)
        doc.add_node(para)

    def _add_image(self, doc: CanonicalDocument, page: PageNode, block: dict, order: int) -> None:
        img_bytes = block.get("image") or b""
        # Content-addressed key. parse is sync but blob.put is async, so we stash the bytes on the
        # document (transient) keyed by blob_ref; the async upload route drains _pending_assets,
        # writes them to blob storage, and flips persisted → True.
        digest = hashlib.sha256(img_bytes).hexdigest()[:16] if img_bytes else "empty"
        blob_ref = f"images/{digest}"
        node = ImageNode(
            id=new_node_id("img"),
            parent_id=page.id,
            reading_order=order,
            blob_ref=blob_ref,
            mime=f"image/{block.get('ext', 'png')}",
            bbox=_bbox(block.get("bbox")),
            attrs={"persisted": False, "width": block.get("width"), "height": block.get("height")},
        )
        if img_bytes:
            doc._pending_assets[blob_ref] = img_bytes
        page.children.append(node.id)
        doc.add_node(node)

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError(
            "PdfAdapter.render_preview needs source bytes — use render_preview_bytes(data, page)"
        )

    def render_preview_bytes(self, data: bytes, page: int = 0, *, scale: float = 1.5) -> bytes:
        """Rasterise a page to PNG bytes for the canvas backdrop."""
        pdf = fitz.open(stream=data, filetype="pdf")
        try:
            pixmap = pdf[page].get_pixmap(matrix=fitz.Matrix(scale, scale))
            return pixmap.tobytes("png")
        finally:
            pdf.close()

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("PdfAdapter.export — write-back via incremental save is deferred")


def _bbox(raw) -> BBox | None:
    if not raw or len(raw) != 4:
        return None
    x0, y0, x1, y1 = raw
    return BBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))


def _color(raw) -> str | None:
    if raw is None:
        return None
    try:
        return "#%06x" % (int(raw) & 0xFFFFFF)
    except (ValueError, TypeError):
        return None
