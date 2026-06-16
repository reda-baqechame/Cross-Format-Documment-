"""Universal canonical-model → DOCX writer.

Rebuilds a real ``.docx`` from the node graph regardless of the source format, so a
PDF- or TXT-origin document can be downloaded as Word. It is intentionally tolerant:
unknown node types are skipped and missing formatting is simply omitted rather than
raising, because fidelity-best-effort beats a hard failure on an unusual document.
"""

from __future__ import annotations

import io

from docx import Document as DocxDocument
from docx.shared import Pt

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import run_text


def model_to_docx(doc: CanonicalDocument) -> bytes:
    out = DocxDocument()
    if doc.meta.title:
        out.core_properties.title = doc.meta.title

    pages_seen = 0
    for node in doc.children_of(doc.root_id):
        if node.type == "page":
            if pages_seen:
                out.add_page_break()
            pages_seen += 1
        _write_block(out, doc, node)

    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def _write_block(out: DocxDocument, doc: CanonicalDocument, node: AnyNode) -> None:
    kind = node.type

    if kind in ("root", "page"):
        for child in doc.children_of(node.id):
            _write_block(out, doc, child)

    elif kind == "heading":
        level = min(max(int(getattr(node, "level", 1) or 1), 0), 9)
        para = out.add_heading("", level=level)
        _add_runs(para, doc, node)

    elif kind == "paragraph":
        _add_runs(out.add_paragraph(), doc, node)

    elif kind == "list":
        ordered = bool(getattr(node, "ordered", False))
        style = "List Number" if ordered else "List Bullet"
        for item in doc.children_of(node.id):
            if item.type == "list_item":
                _add_runs(out.add_paragraph(style=style), doc, item)

    elif kind == "list_item":
        _add_runs(out.add_paragraph(style="List Bullet"), doc, node)

    elif kind == "table":
        _write_table(out, doc, node)

    elif kind == "image":
        alt = getattr(node, "alt_text", None) or "image"
        out.add_paragraph(f"[image: {alt}]")

    elif kind == "field":
        name = getattr(node, "field_name", "field")
        value = getattr(node, "value", None) or ""
        out.add_paragraph(f"{name}: {value}")

    # comment / annotation / metadata_block / run are not emitted as standalone blocks.


def _add_runs(para, doc: CanonicalDocument, block: AnyNode) -> None:
    for child in doc.children_of(block.id):
        if child.type != "run":
            continue
        text = run_text(doc, child)
        if not text:
            continue
        run = para.add_run(text)
        run.bold = bool(getattr(child, "bold", False))
        run.italic = bool(getattr(child, "italic", False))
        run.underline = bool(getattr(child, "underline", False))
        font_name = getattr(child, "font", None)
        if font_name:
            run.font.name = font_name
        size = getattr(child, "size", None)
        if size:
            run.font.size = Pt(float(size))


def _write_table(out: DocxDocument, doc: CanonicalDocument, tnode: AnyNode) -> None:
    rows = [n for n in doc.children_of(tnode.id) if n.type == "table_row"]
    if not rows:
        return
    ncols = max(
        (sum(1 for c in doc.children_of(r.id) if c.type == "table_cell") for r in rows),
        default=0,
    )
    if ncols == 0:
        return

    table = out.add_table(rows=len(rows), cols=ncols)
    for ri, row in enumerate(rows):
        cells = [c for c in doc.children_of(row.id) if c.type == "table_cell"]
        for ci, cell in enumerate(cells):
            if ci >= ncols:
                break
            text = "".join(
                run_text(doc, rn) for rn in doc.children_of(cell.id) if rn.type == "run"
            )
            table.cell(ri, ci).text = text
