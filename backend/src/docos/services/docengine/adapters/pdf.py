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
from docos.model.nodes import (
    ImageNode,
    PageNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
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

            # Cap per-page table detection so a pathological many-page PDF can't exhaust CPU.
            from docos.settings import get_settings

            max_scan = get_settings().max_scan_pages

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

                self._add_page_content(doc, pnode, page, detect_tables=pno < max_scan)

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

    def _add_page_content(
        self, doc: CanonicalDocument, page: PageNode, src, *, detect_tables: bool = True
    ) -> None:
        """Lay out a page's tables, text blocks and images in vertical reading order.

        Tables are detected first; text/image blocks that fall inside a detected table region
        are dropped so their content isn't duplicated outside the table.
        """
        tables = self._find_tables(src) if detect_tables else []
        table_rects = [t["rect"] for t in tables]

        # (y0, x0, kind, payload) for everything on the page, then sort top-to-bottom.
        items: list[tuple[float, float, str, object]] = [
            (t["rect"].y0, t["rect"].x0, "table", t) for t in tables
        ]
        for block in src.get_text("dict").get("blocks", []):
            bbox = block.get("bbox")
            if bbox and _inside_any(bbox, table_rects):
                continue
            y0 = float(bbox[1]) if bbox else 0.0
            x0 = float(bbox[0]) if bbox else 0.0
            kind = "image" if block.get("type") == 1 else "text"
            items.append((y0, x0, kind, block))

        items.sort(key=lambda it: (round(it[0], 1), round(it[1], 1)))
        for order, (_y, _x, kind, payload) in enumerate(items):
            if kind == "table":
                self._add_table(doc, page, payload, order)  # type: ignore[arg-type]
            elif kind == "image":
                self._add_image(doc, page, payload, order)  # type: ignore[arg-type]
            else:
                self._add_text_block(doc, page, payload, order)  # type: ignore[arg-type]

    def _find_tables(self, src) -> list[dict]:
        """Detect tables on a page via PyMuPDF; degrade to [] on old fitz or any failure."""
        if not hasattr(src, "find_tables"):
            return []
        try:
            finder = src.find_tables()
        except Exception:  # noqa: BLE001 - table detection is best-effort, never fatal
            return []
        out: list[dict] = []
        for table in getattr(finder, "tables", []):
            try:
                rows = table.extract()
                rect = fitz.Rect(table.bbox)
            except Exception:  # noqa: BLE001 - skip a malformed table, keep the rest
                continue
            # Require at least one non-empty cell so a stray ruling line isn't a "table".
            if rows and any(any((c or "").strip() for c in row) for row in rows):
                out.append({"rect": rect, "rows": rows})
        return out

    def _add_table(self, doc: CanonicalDocument, page: PageNode, tdata: dict, order: int) -> None:
        rows: list[list] = tdata["rows"]
        ncols = max((len(r) for r in rows), default=0)
        tnode = TableNode(
            id=new_node_id(),
            parent_id=page.id,
            reading_order=order,
            bbox=_bbox(tuple(tdata["rect"])),
            rows=len(rows),
            cols=ncols,
        )
        page.children.append(tnode.id)
        doc.add_node(tnode)
        for ri, row in enumerate(rows):
            rnode = TableRowNode(id=new_node_id(), parent_id=tnode.id, row=ri, reading_order=ri)
            tnode.children.append(rnode.id)
            doc.add_node(rnode)
            for ci, cell in enumerate(row):
                cnode = TableCellNode(
                    id=new_node_id(), parent_id=rnode.id, row=ri, col=ci, reading_order=ci
                )
                run = RunNode(id=new_node_id(), parent_id=cnode.id, text=(cell or "").strip())
                cnode.children.append(run.id)
                rnode.children.append(cnode.id)
                doc.add_node(cnode)
                doc.add_node(run)

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError(
            "PdfAdapter.render_preview needs source bytes — use render_preview_bytes(data, page)"
        )

    def render_preview_bytes(
        self, data: bytes, page: int = 0, *, scale: float | None = None
    ) -> bytes:
        """Rasterise a page to PNG bytes for the canvas backdrop."""
        pages = self.rasterize_pages(data, [page], scale=scale)
        if page not in pages:
            raise IndexError(f"page {page} out of range")
        return pages[page]

    def rasterize_pages(
        self,
        data: bytes,
        page_indices: list[int],
        *,
        scale: float | None = None,
        max_pages: int | None = None,
    ) -> dict[int, bytes]:
        """Rasterise pages in one ``fitz.open`` call — avoids OOM from reopening huge PDFs."""
        from docos.settings import get_settings

        settings = get_settings()
        scale = settings.pdf_raster_scale if scale is None else scale
        cap = settings.max_searchable_raster_pages if max_pages is None else max_pages
        max_side = settings.pdf_raster_max_side_px
        indices = [i for i in page_indices if i >= 0][:cap]

        pdf = fitz.open(stream=data, filetype="pdf")
        out: dict[int, bytes] = {}
        try:
            for i in indices:
                if i >= pdf.page_count:
                    continue
                page = pdf[i]
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                if max_side and max(pix.width, pix.height) > max_side:
                    ratio = max_side / float(max(pix.width, pix.height))
                    mat = fitz.Matrix(scale * ratio, scale * ratio)
                    pix = page.get_pixmap(matrix=mat)
                out[i] = pix.tobytes("png")
        finally:
            pdf.close()
        return out

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("PdfAdapter.export — write-back via incremental save is deferred")


def _inside_any(bbox, rects) -> bool:
    """True if a block's centre falls inside any of the given table rectangles."""
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return any(r.x0 <= cx <= r.x1 and r.y0 <= cy <= r.y1 for r in rects)


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
