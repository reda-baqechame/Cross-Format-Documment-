"""Canonical-model → Markdown / HTML / CSV writers.

These give the product the "convert anything to anything" breadth competitors charge
for: any opened format (PDF, DOCX, XLSX, scan…) downloads as clean Markdown, HTML, or
CSV because every format already lives in one node graph. Redaction is honored through
``run_text`` exactly like the DOCX/PDF writers — redacted content never reaches output.
"""

from __future__ import annotations

import csv
import html
import io

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import (
    is_redacted,
    node_text,
    run_text,
    safe_link_href,
    spreadsheet_text,
)


def _runs(doc: CanonicalDocument, block: AnyNode) -> list[AnyNode]:
    return [c for c in doc.children_of(block.id) if c.type == "run"]


def _plain(doc: CanonicalDocument, block: AnyNode) -> str:
    return _inline_plain(doc, block).strip()


def _inline_plain(doc: CanonicalDocument, block: AnyNode) -> str:
    parts: list[str] = []
    for child in doc.children_of(block.id):
        if child.type == "run":
            parts.append(run_text(doc, child))
        elif child.type == "footnote_reference" and not is_redacted(doc, child.id):
            parts.append(f"[{getattr(child, 'marker', '')}]")
        elif child.type == "unsupported":
            parts.append(f"[unsupported: {getattr(child, 'original_type', 'unknown')}]")
    return "".join(parts)


def _footnote_lines(doc: CanonicalDocument) -> list[str]:
    lines: list[str] = []
    for note in doc.nodes.values():
        if note.type != "footnote" or is_redacted(doc, note.id):
            continue
        text_parts: list[str] = []
        direct = _inline_plain(doc, note).strip()
        if direct:
            text_parts.append(direct)
        for child in doc.children_of(note.id):
            if child.type in ("paragraph", "heading", "table_cell"):
                text = _inline_plain(doc, child).strip()
                if text:
                    text_parts.append(text)
        marker = getattr(note, "marker", "")
        text = " ".join(text_parts).strip()
        if text:
            lines.append(f"{marker}. {text}")
    return lines


# ── Markdown ──────────────────────────────────────────────────────────────────
def model_to_markdown(doc: CanonicalDocument) -> bytes:
    lines: list[str] = []
    for node in doc.children_of(doc.root_id):
        if node.type == "footnote":
            continue
        _md_block(lines, doc, node)
    footnotes = _footnote_lines(doc)
    if footnotes:
        lines.append("## Footnotes")
        lines.append("")
        for line in footnotes:
            marker, _, text = line.partition(". ")
            lines.append(f"[^{marker}]: {text}")
        lines.append("")
    text = "\n".join(lines).strip() + "\n"
    return text.encode("utf-8")


def _md_runs(doc: CanonicalDocument, block: AnyNode) -> str:
    parts: list[str] = []
    for r in doc.children_of(block.id):
        if r.type == "footnote_reference":
            if not is_redacted(doc, r.id):
                parts.append(f"[^{getattr(r, 'marker', '')}]")
            continue
        if r.type == "unsupported":
            parts.append(f"[unsupported: {getattr(r, 'original_type', 'unknown')}]")
            continue
        if r.type != "run":
            continue
        text = run_text(doc, r)
        if not text:
            continue
        if getattr(r, "bold", False) and getattr(r, "italic", False):
            text = f"***{text}***"
        elif getattr(r, "bold", False):
            text = f"**{text}**"
        elif getattr(r, "italic", False):
            text = f"*{text}*"
        href = safe_link_href(getattr(r, "link_href", None))
        if href:
            text = f"[{text}]({href})"
        parts.append(text)
    return "".join(parts).strip()


def _md_block(lines: list[str], doc: CanonicalDocument, node: AnyNode) -> None:
    kind = node.type
    if kind in ("root", "page"):
        for child in doc.children_of(node.id):
            _md_block(lines, doc, child)
    elif kind == "heading":
        level = min(max(int(getattr(node, "level", 1) or 1), 1), 6)
        lines.append(f"{'#' * level} {_md_runs(doc, node)}")
        lines.append("")
    elif kind == "paragraph":
        text = _md_runs(doc, node)
        if text:
            lines.append(text)
            lines.append("")
    elif kind == "list":
        ordered = bool(getattr(node, "ordered", False))
        for i, item in enumerate(c for c in doc.children_of(node.id) if c.type == "list_item"):
            marker = f"{i + 1}." if ordered else "-"
            lines.append(f"{marker} {_md_runs(doc, item)}")
        lines.append("")
    elif kind == "table":
        _md_table(lines, doc, node)
    elif kind == "image":
        if not is_redacted(doc, node.id):
            lines.append(f"![{node_text(doc, node) or 'image'}]()")
            lines.append("")
    elif kind == "field":
        if not is_redacted(doc, node.id):
            lines.append(f"**{getattr(node, 'field_name', 'field')}:** {node_text(doc, node)}")
            lines.append("")
    elif kind == "unsupported":
        lines.append(f"[unsupported node: {getattr(node, 'original_type', 'unknown')}]")
        for child in doc.children_of(node.id):
            _md_block(lines, doc, child)


def _table_rows(doc: CanonicalDocument, tnode: AnyNode) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in (n for n in doc.children_of(tnode.id) if n.type == "table_row"):
        cells = [c for c in doc.children_of(row.id) if c.type == "table_cell"]
        rows.append([_plain(doc, cell) for cell in cells])
    return rows


def _md_table(lines: list[str], doc: CanonicalDocument, tnode: AnyNode) -> None:
    rows = _table_rows(doc, tnode)
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    header, *body = rows
    lines.append("| " + " | ".join(c.replace("|", "\\|") for c in header) + " |")
    lines.append("| " + " | ".join(["---"] * ncols) + " |")
    for r in body:
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
    lines.append("")


# ── HTML ──────────────────────────────────────────────────────────────────────
def model_to_html(doc: CanonicalDocument) -> bytes:
    body: list[str] = []
    for node in doc.children_of(doc.root_id):
        if node.type == "footnote":
            continue
        _html_block(body, doc, node)
    footnotes = _footnote_lines(doc)
    if footnotes:
        items = []
        for line in footnotes:
            marker, _, text = line.partition(". ")
            items.append(f'<li id="fn-{html.escape(marker)}">{html.escape(text)}</li>')
        body.append(
            '<section class="footnotes"><h2>Footnotes</h2><ol>'
            + "".join(items)
            + "</ol></section>"
        )
    title = html.escape(doc.meta.title or "Document")
    page = (
        '<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n'
        f"<title>{title}</title>\n</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )
    return page.encode("utf-8")


def _html_runs(doc: CanonicalDocument, block: AnyNode) -> str:
    parts: list[str] = []
    for r in doc.children_of(block.id):
        if r.type == "footnote_reference":
            if not is_redacted(doc, r.id):
                marker = html.escape(getattr(r, "marker", ""))
                parts.append(f'<sup id="fnref-{marker}">{marker}</sup>')
            continue
        if r.type == "unsupported":
            label = html.escape(getattr(r, "original_type", "unknown"))
            parts.append(f'<span data-node-type="unsupported">[unsupported: {label}]</span>')
            continue
        if r.type != "run":
            continue
        text = run_text(doc, r)
        if not text:
            continue
        text = html.escape(text)
        if getattr(r, "bold", False):
            text = f"<strong>{text}</strong>"
        if getattr(r, "italic", False):
            text = f"<em>{text}</em>"
        if getattr(r, "underline", False):
            text = f"<u>{text}</u>"
        href = safe_link_href(getattr(r, "link_href", None))
        if href:
            text = f'<a href="{html.escape(href, quote=True)}">{text}</a>'
        parts.append(text)
    return "".join(parts)


def _html_block(body: list[str], doc: CanonicalDocument, node: AnyNode) -> None:
    kind = node.type
    if kind in ("root", "page"):
        for child in doc.children_of(node.id):
            _html_block(body, doc, child)
    elif kind == "heading":
        level = min(max(int(getattr(node, "level", 1) or 1), 1), 6)
        body.append(f"<h{level}>{_html_runs(doc, node)}</h{level}>")
    elif kind == "paragraph":
        inner = _html_runs(doc, node)
        if inner:
            body.append(f"<p>{inner}</p>")
    elif kind == "list":
        tag = "ol" if getattr(node, "ordered", False) else "ul"
        items = [
            f"<li>{_html_runs(doc, item)}</li>"
            for item in doc.children_of(node.id)
            if item.type == "list_item"
        ]
        body.append(f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>")
    elif kind == "table":
        rows = _table_rows(doc, node)
        if rows:
            trs = [
                "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows
            ]
            body.append("<table>\n" + "\n".join(trs) + "\n</table>")
    elif kind == "image":
        if not is_redacted(doc, node.id):
            body.append(f"<p>[image: {html.escape(node_text(doc, node) or 'image')}]</p>")
    elif kind == "field":
        if not is_redacted(doc, node.id):
            name = html.escape(getattr(node, "field_name", "field"))
            value = html.escape(node_text(doc, node))
            body.append(f"<p><strong>{name}:</strong> {value}</p>")
    elif kind == "unsupported":
        label = html.escape(getattr(node, "original_type", "unknown"))
        body.append(f'<div data-node-type="unsupported">[unsupported node: {label}]</div>')
        for child in doc.children_of(node.id):
            _html_block(body, doc, child)


# ── RTF ─────────────────────────────────────────────────────────────────────────
def _rtf_escape(text: str) -> str:
    """Escape RTF control chars and emit non-ASCII as portable ``\\uN?`` unicode escapes."""
    out: list[str] = []
    for ch in text:
        if ch in ("\\", "{", "}"):
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\par ")
        elif ch == "\t":
            out.append("\\tab ")
        elif ord(ch) < 128:
            out.append(ch)
        else:
            code = ord(ch)
            code = code if code <= 32767 else code - 65536  # RTF \u takes a signed 16-bit int
            out.append(f"\\u{code}?")
    return "".join(out)


def _rtf_runs(doc: CanonicalDocument, block: AnyNode) -> str:
    parts: list[str] = []
    for r in doc.children_of(block.id):
        if r.type == "footnote_reference":
            if not is_redacted(doc, r.id):
                parts.append("\\super " + _rtf_escape(getattr(r, "marker", "")) + "\\nosupersub ")
            continue
        if r.type == "unsupported":
            parts.append(_rtf_escape(f"[unsupported: {getattr(r, 'original_type', 'unknown')}]"))
            continue
        if r.type != "run":
            continue
        text = run_text(doc, r)
        if not text:
            continue
        esc = _rtf_escape(text)
        if getattr(r, "bold", False):
            esc = "{\\b " + esc + "}"
        if getattr(r, "italic", False):
            esc = "{\\i " + esc + "}"
        parts.append(esc)
    return "".join(parts)


def _rtf_block(parts: list[str], doc: CanonicalDocument, node: AnyNode) -> None:
    kind = node.type
    if kind in ("root", "page"):
        for child in doc.children_of(node.id):
            _rtf_block(parts, doc, child)
    elif kind == "heading":
        inner = _rtf_runs(doc, node)
        if inner:
            parts.append("{\\b\\fs32 " + inner + "}\\par")
    elif kind == "paragraph":
        inner = _rtf_runs(doc, node)
        if inner:
            parts.append(inner + "\\par")
    elif kind == "list":
        ordered = bool(getattr(node, "ordered", False))
        i = 0
        for item in doc.children_of(node.id):
            if item.type != "list_item":
                continue
            i += 1
            marker = f"{i}. " if ordered else "\\bullet  "
            parts.append(marker + _rtf_runs(doc, item) + "\\par")
    elif kind == "table":
        for row in _table_rows(doc, node):
            parts.append("\\tab ".join(_rtf_escape(cell) for cell in row) + "\\par")
    elif kind == "image":
        if not is_redacted(doc, node.id):
            parts.append(_rtf_escape(f"[image: {node_text(doc, node) or 'image'}]") + "\\par")
    elif kind == "field":
        if not is_redacted(doc, node.id):
            name = _rtf_escape(getattr(node, "field_name", "field"))
            parts.append("{\\b " + name + ":} " + _rtf_escape(node_text(doc, node)) + "\\par")
    elif kind == "unsupported":
        label = getattr(node, "original_type", "unknown")
        parts.append(_rtf_escape(f"[unsupported node: {label}]") + "\\par")
        for child in doc.children_of(node.id):
            _rtf_block(parts, doc, child)


def model_to_rtf(doc: CanonicalDocument) -> bytes:
    """Rebuild a real ``.rtf`` from the node graph — paragraphs, bold/italic runs, headings,
    lists, tables (tab-separated), with redaction honored via ``run_text``."""
    parts: list[str] = []
    for node in doc.children_of(doc.root_id):
        if node.type == "footnote":
            continue
        _rtf_block(parts, doc, node)
    footnotes = _footnote_lines(doc)
    if footnotes:
        parts.append("{\\b Footnotes}\\par")
        for line in footnotes:
            parts.append(_rtf_escape(line) + "\\par")
    rtf = "{\\rtf1\\ansi\\deff0\n" + "\n".join(parts) + "\n}"
    # Non-ASCII is already \uN?-escaped, so ASCII encoding is lossless here.
    return rtf.encode("ascii", errors="replace")


# ── CSV ─────────────────────────────────────────────────────────────────────────
def model_to_csv(doc: CanonicalDocument) -> bytes:
    """Tables become CSV rows; if the document has no tables, each paragraph is a row."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    wrote = False
    for tnode in doc.walk():
        if tnode.type == "table":
            for row in _table_rows(doc, tnode):
                writer.writerow([spreadsheet_text(cell) for cell in row])
            wrote = True
    if not wrote:
        for node in doc.walk():
            if node.type in ("paragraph", "heading"):
                text = _plain(doc, node)
                if text:
                    writer.writerow([spreadsheet_text(text)])
    return buf.getvalue().encode("utf-8")
