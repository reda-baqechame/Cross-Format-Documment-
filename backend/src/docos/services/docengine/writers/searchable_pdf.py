"""Canonical-model → searchable PDF.

Two paths, one writer, both producing genuinely selectable/searchable output:

* **Scan overlay** — when a page has a backing image (a scanned page), the image is drawn
  as the visible layer and the recovered text (from OCR at ingest) is laid down as an
  *invisible* text layer on top. This is exactly how an OCR'd PDF works: you see the scan,
  but the text is selectable and searchable.
* **Born-digital** — with no backing image (TXT/DOCX/… or any model-only document), the
  text is rendered visibly, so the result is a clean, fully selectable PDF.

Redaction is honored through ``run_text`` — redacted content never reaches the output,
the same guarantee every other writer makes.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import run_text

_A4 = (595.0, 842.0)  # points
_MARGIN = 54.0  # ¾ inch
_FONTSIZE = 11.0
_INVISIBLE = 3  # PDF text render mode: neither fill nor stroke (OCR text layer)


def _lines_under(doc: CanonicalDocument, start_id: str) -> list[str]:
    """Visible text lines (reading order) for everything under ``start_id``."""
    lines: list[str] = []
    for node in doc.walk(start_id):
        if node.type in ("paragraph", "heading", "list_item"):
            text = _block_text(doc, node)
            if text:
                lines.append(text)
        elif node.type == "table_cell":
            text = _block_text(doc, node)
            if text:
                lines.append(text)
        elif node.type == "field":
            name = getattr(node, "field_name", "field")
            value = getattr(node, "value", "") or ""
            lines.append(f"{name}: {value}")
    return lines


def _block_text(doc: CanonicalDocument, block: AnyNode) -> str:
    return "".join(run_text(doc, r) for r in doc.children_of(block.id) if r.type == "run").strip()


# Pages with substantial extracted text use born-digital rendering; raster is only for scans.
_MIN_RASTER_TEXT_CHARS = 10


def pages_needing_raster(doc: CanonicalDocument, page_nodes: list[AnyNode]) -> list[int]:
    """0-based page indices that need a raster backdrop (image scan / empty OCR page)."""
    indices: list[int] = []
    for idx, pnode in enumerate(page_nodes):
        lines = _lines_under(doc, pnode.id)
        text_len = sum(len(line) for line in lines)
        has_image = any(n.type == "image" for n in doc.children_of(pnode.id))
        if has_image or text_len < _MIN_RASTER_TEXT_CHARS:
            indices.append(idx)
    return indices


def _write_text(page: fitz.Page, lines: list[str], *, invisible: bool) -> None:
    if not lines:
        return
    rect = fitz.Rect(_MARGIN, _MARGIN, page.rect.width - _MARGIN, page.rect.height - _MARGIN)
    page.insert_textbox(
        rect,
        "\n".join(lines),
        fontsize=_FONTSIZE,
        fontname="helv",
        render_mode=_INVISIBLE if invisible else 0,
        align=0,
    )


def model_to_searchable_pdf(
    doc: CanonicalDocument, page_images: dict[int, bytes] | None = None
) -> bytes:
    """Render the document to a searchable PDF.

    ``page_images`` maps a 0-based page index to image bytes; when present for a page,
    that image is drawn and the text becomes an invisible overlay (scan → searchable).
    """
    page_images = page_images or {}
    out = fitz.open()

    page_nodes = [n for n in doc.children_of(doc.root_id) if n.type == "page"]

    if page_nodes:
        for idx, pnode in enumerate(page_nodes):
            width = float(getattr(pnode, "width", 0) or 0) or _A4[0]
            height = float(getattr(pnode, "height", 0) or 0) or _A4[1]
            page = out.new_page(width=width, height=height)
            image = page_images.get(idx)
            if image:
                try:
                    page.insert_image(page.rect, stream=image)
                except Exception:  # noqa: BLE001 - a bad image must not fail the export
                    image = None
            _write_text(page, _lines_under(doc, pnode.id), invisible=bool(image))
    else:
        # No page structure (e.g. TXT/DOCX): a single born-digital page of selectable text.
        page = out.new_page(width=_A4[0], height=_A4[1])
        _write_text(page, _lines_under(doc, doc.root_id), invisible=False)

    data = out.tobytes()
    out.close()
    return data
