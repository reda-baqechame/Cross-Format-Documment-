"""Docling-backed parsing seam (Docling is MIT-licensed).

Docling turns PDF/DOCX/PPTX/XLSX into a rich structured representation — layout blocks, reading
order, and real table structure — which is stronger than the built-in adapters on messy, real
business files. This module wires it in **without** changing how documents are exported or
previewed: the ``Docling*Adapter`` classes subclass the corresponding native adapter and override
**only** ``parse``, so ``format_id``, ``render_preview`` and ``export`` keep using native code.

It is an *optional* dependency (``pip install "docling>=2.0"``) and an *activatable* seam: it runs
only when ``PARSER_ENGINE=docling`` and the ``docling`` package is importable. On any failure —
Docling
missing, an unsupported file, a conversion error — it transparently falls back to the native
adapter, so uploads never break and the offline default is untouched.

The Docling→canonical mapping (:func:`docling_dict_to_canonical`) consumes the stable
``DoclingDocument.export_to_dict()`` shape and is pure/unit-tested, so it is covered without the
native dependency installed.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import (
    HeadingNode,
    ImageNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.docengine.adapters.docx import DocxAdapter
from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.adapters.pptx import PptxAdapter
from docos.services.docengine.adapters.xlsx import XlsxAdapter
from docos.storage.blob import BlobStore

logger = logging.getLogger("docos.docengine.docling")

# Docling text labels that should become headings, with their default level.
_HEADING_LABELS = {"title": 1, "section_header": 2, "subtitle": 2}


def docling_available() -> bool:
    """True when the optional ``docling`` package can be imported."""
    try:
        import docling  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency; absence is the common case
        return False
    return True


def _convert_to_dict(data: bytes) -> dict[str, Any]:
    """Run Docling on raw bytes and return ``DoclingDocument.export_to_dict()`` (may raise)."""
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    stream = DocumentStream(name="upload", stream=io.BytesIO(data))
    result = DocumentConverter().convert(stream)
    return result.document.export_to_dict()


def _ref_id(ref: dict[str, Any]) -> str | None:
    """Body children reference items via ``$ref`` (newer) or ``cref`` (older) — accept both."""
    return ref.get("$ref") or ref.get("cref")


def _index_items(d: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map every ``self_ref`` (e.g. ``#/texts/0``) to its ``(kind, item)`` for body-order lookup."""
    index: dict[str, tuple[str, dict[str, Any]]] = {}
    for kind in ("texts", "tables", "pictures"):
        for i, item in enumerate(d.get(kind, []) or []):
            ref = item.get("self_ref") or f"#/{kind}/{i}"
            index[ref] = (kind, item)
    return index


def _ordered_items(d: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(kind, item)`` pairs in document reading order.

    Prefers the explicit ``body.children`` order; falls back to texts-then-tables-then-pictures
    when a body is absent (older/partial exports).
    """
    index = _index_items(d)
    body = d.get("body") or {}
    children = body.get("children") or []
    ordered: list[tuple[str, dict[str, Any]]] = []
    for ref in children:
        rid = _ref_id(ref) if isinstance(ref, dict) else None
        if rid and rid in index:
            ordered.append(index[rid])
    if ordered:
        return ordered
    return [
        (kind, item) for kind in ("texts", "tables", "pictures") for item in (d.get(kind, []) or [])
    ]


def _add_text_item(
    doc: CanonicalDocument, root: RootNode, item: dict[str, Any], order: int
) -> None:
    text = (item.get("text") or "").strip()
    if not text:
        return
    label = item.get("label") or "paragraph"
    if label in _HEADING_LABELS:
        level = int(item.get("level") or _HEADING_LABELS[label])
        level = max(1, min(6, level))
        node: HeadingNode | ParagraphNode = HeadingNode(
            id=new_node_id("h"), parent_id=root.id, level=level, reading_order=order
        )
        node.tags.append(f"H{level}")
    else:
        node = ParagraphNode(id=new_node_id("p"), parent_id=root.id, reading_order=order)
        if label == "list_item":
            node.tags.append("list_item")
    run = RunNode(id=new_node_id("run"), parent_id=node.id, text=text)
    node.children.append(run.id)
    root.children.append(node.id)
    doc.add_node(node)
    doc.add_node(run)


def _add_table_item(
    doc: CanonicalDocument, root: RootNode, item: dict[str, Any], order: int
) -> None:
    data = item.get("data") or {}
    cells = data.get("table_cells") or data.get("cells") or []
    if not cells:
        return
    num_rows = int(
        data.get("num_rows")
        or (max((c.get("start_row_offset_idx", 0) for c in cells), default=-1) + 1)
    )
    num_cols = int(
        data.get("num_cols")
        or (max((c.get("start_col_offset_idx", 0) for c in cells), default=-1) + 1)
    )
    if num_rows <= 0 or num_cols <= 0:
        return
    table = TableNode(
        id=new_node_id("tbl"), parent_id=root.id, rows=num_rows, cols=num_cols, reading_order=order
    )
    root.children.append(table.id)
    doc.add_node(table)

    rows: list[TableRowNode] = []
    for ri in range(num_rows):
        rnode = TableRowNode(id=new_node_id("tr"), parent_id=table.id, row=ri, reading_order=ri)
        table.children.append(rnode.id)
        doc.add_node(rnode)
        rows.append(rnode)

    for cell in cells:
        ri = int(cell.get("start_row_offset_idx", 0))
        ci = int(cell.get("start_col_offset_idx", 0))
        if not (0 <= ri < num_rows and 0 <= ci < num_cols):
            continue
        is_header = bool(cell.get("column_header") or cell.get("row_header"))
        cnode = TableCellNode(
            id=new_node_id("td"),
            parent_id=rows[ri].id,
            row=ri,
            col=ci,
            row_span=max(1, int(cell.get("row_span", 1))),
            col_span=max(1, int(cell.get("col_span", 1))),
            header=is_header,
        )
        text = (cell.get("text") or "").strip()
        if text:
            run = RunNode(id=new_node_id("run"), parent_id=cnode.id, text=text)
            cnode.children.append(run.id)
            doc.add_node(run)
        rows[ri].children.append(cnode.id)
        doc.add_node(cnode)


def _add_picture_item(
    doc: CanonicalDocument, root: RootNode, item: dict[str, Any], order: int
) -> None:
    """Represent a Docling picture as an (unpersisted) placeholder image node for layout fidelity.

    Embedding the actual bytes from Docling is tracked in the roadmap; here we keep the structural
    slot so reading order and accessibility tagging stay correct.
    """
    img = ImageNode(
        id=new_node_id("img"),
        parent_id=root.id,
        blob_ref="docling-picture",
        mime="image/png",
        reading_order=order,
        attrs={"persisted": False, "source": "docling"},
    )
    root.children.append(img.id)
    doc.add_node(img)


def docling_dict_to_canonical(
    d: dict[str, Any], *, source_format: str, source_mime: str
) -> CanonicalDocument:
    """Map a ``DoclingDocument.export_to_dict()`` payload into a :class:`CanonicalDocument`.

    Pure and dependency-free so it is fully unit-testable without Docling installed.
    """
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    pages = d.get("pages")
    page_count = len(pages) if isinstance(pages, dict) else 0
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            title=(d.get("name") or None),
            source_format=source_format,
            source_mime=source_mime,
            created_at=now,
            modified_at=now,
            page_count=page_count,
            custom={"parsed_by": "docling"},
        ),
    )
    doc.add_node(root)

    for order, (kind, item) in enumerate(_ordered_items(d)):
        if kind == "texts":
            _add_text_item(doc, root, item, order)
        elif kind == "tables":
            _add_table_item(doc, root, item, order)
        elif kind == "pictures":
            _add_picture_item(doc, root, item, order)
    if len(doc.nodes) > 1:
        doc.accessibility.tagged = True
    return doc


def parse_with_docling(
    data: bytes,
    *,
    source_format: str,
    source_mime: str,
    convert_fn: Callable[[bytes], dict[str, Any]] | None = None,
) -> CanonicalDocument:
    """Convert bytes via Docling and map the result (raises if conversion fails).

    ``convert_fn`` is injectable so the mapping can be tested with a recorded Docling dict.
    """
    payload = (convert_fn or _convert_to_dict)(data)
    return docling_dict_to_canonical(payload, source_format=source_format, source_mime=source_mime)


class _DoclingMixin:
    """Overrides ``parse`` to use Docling, falling back to the native adapter on any failure."""

    format_id: str
    supported_mimes: tuple[str, ...]

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        if docling_available():
            try:
                return parse_with_docling(
                    data,
                    source_format=self.format_id,
                    source_mime=self.supported_mimes[0],
                )
            except Exception as exc:  # noqa: BLE001 - any Docling failure falls back to native
                logger.warning("docling parse failed (%s); falling back to native", exc)
        return super().parse(data, blob=blob)  # type: ignore[misc]


class DoclingPdfAdapter(_DoclingMixin, PdfAdapter):
    pass


class DoclingDocxAdapter(_DoclingMixin, DocxAdapter):
    pass


class DoclingPptxAdapter(_DoclingMixin, PptxAdapter):
    pass


class DoclingXlsxAdapter(_DoclingMixin, XlsxAdapter):
    pass
