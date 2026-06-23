"""Universal canonical-model → PNG writer.

Renders the document's text content onto a white raster page with Pillow, so any
opened document can be downloaded as an image. Headings are drawn slightly larger
and bold-ish (doubled-up); paragraphs and list items wrap to the page width. It
uses Pillow's built-in bitmap font so there is no external font-file dependency.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import run_text

_WIDTH = 816  # ~ US-Letter width at 96 dpi
_MARGIN = 56
_LINE_H = 20
_PARA_GAP = 10
_MAX_HEIGHT = 20000  # guard against pathologically long documents


def _block_text(doc: CanonicalDocument, block: AnyNode) -> str:
    return "".join(run_text(doc, r) for r in doc.children_of(block.id) if r.type == "run")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    for raw in text.split("\n"):
        words = raw.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else f"{cur} {word}"
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _collect_lines(doc: CanonicalDocument, root_id: str | None = None) -> list[tuple[str, bool]]:
    """(text, is_heading) lines in reading order, flattening pages and tables.

    ``root_id`` restricts collection to one subtree (e.g. a single slide/page) for thumbnails.
    """
    out: list[tuple[str, bool]] = []

    def visit(node: AnyNode) -> None:
        kind = node.type
        if kind in ("root", "page"):
            for child in doc.children_of(node.id):
                visit(child)
        elif kind == "heading":
            out.append((_block_text(doc, node), True))
        elif kind == "paragraph":
            out.append((_block_text(doc, node), False))
        elif kind in ("list", "list_item"):
            if kind == "list_item":
                out.append((f"• {_block_text(doc, node)}", False))
            for child in doc.children_of(node.id):
                visit(child)
        elif kind == "table":
            for row in doc.children_of(node.id):
                if row.type != "table_row":
                    continue
                cells = [
                    _block_text(doc, c) for c in doc.children_of(row.id) if c.type == "table_cell"
                ]
                out.append((" | ".join(cells), False))

    start = doc.nodes.get(root_id) if root_id else doc.nodes[doc.root_id]
    if start is None:
        return [("(empty document)", False)]
    visit(start)
    return [(t, h) for (t, h) in out if t.strip()] or [("(empty document)", False)]


def model_to_png(doc: CanonicalDocument, *, root_id: str | None = None) -> bytes:
    """Render the document — or a single subtree (``root_id``, e.g. one slide) — to PNG."""
    font = ImageFont.load_default()
    max_w = _WIDTH - 2 * _MARGIN
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    wrapped: list[tuple[str, bool]] = []
    if doc.meta.title and root_id is None:
        for ln in _wrap(measure, doc.meta.title, font, max_w):
            wrapped.append((ln, True))
        wrapped.append(("", False))
    for text, is_heading in _collect_lines(doc, root_id):
        for ln in _wrap(measure, text, font, max_w):
            wrapped.append((ln, is_heading))
        wrapped.append(("", False))  # paragraph gap

    height = min(_MARGIN * 2 + len(wrapped) * _LINE_H, _MAX_HEIGHT)
    img = Image.new("RGB", (_WIDTH, max(height, 120)), "white")
    draw = ImageDraw.Draw(img)

    y = _MARGIN
    for text, is_heading in wrapped:
        if y > _MAX_HEIGHT - _LINE_H:
            break
        if text:
            draw.text((_MARGIN, y), text, fill="black", font=font)
            if is_heading:  # fake bold by overprinting one pixel right
                draw.text((_MARGIN + 1, y), text, fill="black", font=font)
        y += _LINE_H if text else _PARA_GAP

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
