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

import io

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import run_text

_A4 = (595.0, 842.0)  # points
_MARGIN = 54.0  # ¾ inch
_FONTSIZE = 11.0
_LEADING = 14.0
_INVISIBLE = 3  # PDF text render mode: neither fill nor stroke (OCR text layer)
_FONT = "Helvetica"


def _lines_under(doc: CanonicalDocument, start_id: str) -> list[str]:
    """Visible text lines (reading order) for everything under ``start_id``."""
    lines: list[str] = []
    for node in doc.walk(start_id):
        if node.type == "footnote_reference":
            continue
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
        elif node.type == "footnote":
            text = _footnote_text(doc, node)
            if text:
                lines.append(f"Footnote {getattr(node, 'marker', '')}: {text}")
    return lines


def _block_text(doc: CanonicalDocument, block: AnyNode) -> str:
    parts: list[str] = []
    for child in doc.children_of(block.id):
        if child.type == "run":
            parts.append(run_text(doc, child))
        elif child.type == "footnote_reference":
            parts.append(f"[{getattr(child, 'marker', '')}]")
        elif child.type == "unsupported":
            parts.append(f"[unsupported: {getattr(child, 'original_type', 'unknown')}]")
    return "".join(parts).strip()


def _footnote_text(doc: CanonicalDocument, footnote: AnyNode) -> str:
    lines: list[str] = []
    direct = _block_text(doc, footnote)
    if direct:
        lines.append(direct)
    for child in doc.children_of(footnote.id):
        if child.type in ("paragraph", "heading", "table_cell"):
            text = _block_text(doc, child)
            if text:
                lines.append(text)
    return " ".join(lines).strip()


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


def _wrap(text: str, max_width: float, fontsize: float, string_width) -> list[str]:
    """Greedy word-wrap ``text`` to ``max_width`` points using reportlab's metrics."""
    out: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if line and string_width(trial, _FONT, fontsize) > max_width:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


def _draw_text(canvas, lines: list[str], page_width: float, page_height: float, *, invisible: bool):
    """Lay ``lines`` down the page (wrapped) at the invisible (OCR) or visible render mode."""
    if not lines:
        return
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = canvas.beginText(_MARGIN, page_height - _MARGIN)
    text.setFont(_FONT, _FONTSIZE)
    text.setLeading(_LEADING)
    text.setTextRenderMode(_INVISIBLE if invisible else 0)
    max_width = page_width - 2 * _MARGIN
    for line in lines:
        for wrapped in _wrap(line, max_width, _FONTSIZE, stringWidth):
            text.textLine(wrapped)
    canvas.drawText(text)


def _permissive_searchable_pdf(doc: CanonicalDocument, page_images: dict[int, bytes]) -> bytes:
    """Build the searchable PDF with reportlab (BSD-3) — no AGPL dependency."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    pdf = rl_canvas.Canvas(buf)
    page_nodes = [n for n in doc.children_of(doc.root_id) if n.type == "page"]

    def _emit(width: float, height: float, lines: list[str], image: bytes | None) -> None:
        pdf.setPageSize((width, height))
        drew_image = False
        if image:
            try:
                pdf.drawImage(ImageReader(io.BytesIO(image)), 0, 0, width=width, height=height)
                drew_image = True
            except Exception:  # noqa: BLE001 - a bad image must not fail the export
                drew_image = False
        _draw_text(pdf, lines, width, height, invisible=drew_image)
        pdf.showPage()

    if page_nodes:
        for idx, pnode in enumerate(page_nodes):
            width = float(getattr(pnode, "width", 0) or 0) or _A4[0]
            height = float(getattr(pnode, "height", 0) or 0) or _A4[1]
            _emit(width, height, _lines_under(doc, pnode.id), page_images.get(idx))
    else:
        # No page structure (e.g. TXT/DOCX): a single born-digital page of selectable text.
        _emit(_A4[0], _A4[1], _lines_under(doc, doc.root_id), None)

    pdf.save()
    return buf.getvalue()


def _pymupdf_searchable_pdf(doc: CanonicalDocument, page_images: dict[int, bytes]) -> bytes:
    """Legacy PyMuPDF (AGPL) impl, behind the engine switch until parity becomes the default."""
    import fitz

    def _write_text(page, lines: list[str], *, invisible: bool) -> None:
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
        page = out.new_page(width=_A4[0], height=_A4[1])
        _write_text(page, _lines_under(doc, doc.root_id), invisible=False)
    data = out.tobytes()
    out.close()
    return data


def model_to_searchable_pdf(
    doc: CanonicalDocument, page_images: dict[int, bytes] | None = None
) -> bytes:
    """Render the document to a searchable PDF.

    ``page_images`` maps a 0-based page index to image bytes; when present for a page,
    that image is drawn and the text becomes an invisible overlay (scan → searchable).

    Dispatched by ``settings.pdf_engine``: the permissive (reportlab, BSD-3) writer when selected
    and importable, otherwise the legacy PyMuPDF writer. Both honor redaction via ``run_text``.
    """
    page_images = page_images or {}
    from docos.settings import get_settings

    if get_settings().pdf_engine == "permissive":
        try:
            import reportlab  # noqa: F401

            return _permissive_searchable_pdf(doc, page_images)
        except ModuleNotFoundError:
            pass  # reportlab not installed; fall back to the legacy engine
    return _pymupdf_searchable_pdf(doc, page_images)
