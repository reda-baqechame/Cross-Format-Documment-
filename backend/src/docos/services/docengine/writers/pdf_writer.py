"""PDF write-back — apply the model's edits back onto the original PDF.

Faithful PDF editing is hard because the original font programs and layout engine
aren't reconstructable. The robust, high-fidelity strategy used here is *minimal
rewrite*: re-parse the original PDF to recover each text span's original string, then
touch only the spans that actually changed — redacted runs are truly removed, edited
runs are overwritten in place with their new text, and every untouched span is left
exactly as it was (pixel-perfect). Runs the model added without a bounding box can't
be placed on a fixed page, so they're carried by the DOCX/TXT exports instead.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted

# Rounded-bbox key tolerance: the current model and a fresh re-parse share the same
# extraction geometry, so 1-decimal rounding pairs spans without float drift.
_BoxKey = tuple[int, float, float, float, float]


def _page_number_of(doc: CanonicalDocument, node_id: str | None) -> int | None:
    seen: set[str] = set()
    current = node_id
    while current and current not in seen:
        node = doc.nodes.get(current)
        if node is None:
            return None
        if node.type == "page":
            return getattr(node, "page_number", None)
        seen.add(current)
        current = node.parent_id
    return None


def _box_key(page_number: int, bbox) -> _BoxKey:
    return (page_number, round(bbox.x0, 1), round(bbox.y0, 1), round(bbox.x1, 1), round(bbox.y1, 1))


def _original_text_by_box(data: bytes) -> dict[_BoxKey, str]:
    """Map each original run's rounded box to its text, by re-parsing the source."""
    from docos.services.docengine.adapters.pdf import PdfAdapter

    original = PdfAdapter().parse(data)
    out: dict[_BoxKey, str] = {}
    for node in original.nodes.values():
        if node.type == "run" and node.bbox is not None:
            pno = _page_number_of(original, node.id)
            if pno is not None:
                out[_box_key(pno, node.bbox)] = getattr(node, "text", "")
    return out


def _hex_to_rgb(color: str | None) -> tuple[float, float, float]:
    if not color or not color.startswith("#") or len(color) != 7:
        return (0.0, 0.0, 0.0)
    try:
        r, g, b = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return (r, g, b)
    except ValueError:
        return (0.0, 0.0, 0.0)


def write_back_pdf(data: bytes, doc: CanonicalDocument) -> bytes:
    """Return the original PDF with redactions removed and edited text rewritten."""
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        # Only strip the PDF's embedded /Info + XMP metadata when the model was sanitized
        # (the sanitize_metadata op / "Clean before you send"); plain exports keep it intact.
        sanitized = doc.redaction.metadata_sanitized
        pdf.scrub(
            attached_files=True,
            clean_pages=False,
            embedded_files=True,
            hidden_text=False,
            javascript=True,
            metadata=sanitized,
            redactions=False,
            remove_links=True,
            reset_fields=False,
            reset_responses=True,
            thumbnails=False,
            xml_metadata=sanitized,
        )
        if sanitized:
            pdf.set_metadata({})  # belt-and-suspenders: clear the /Info dict explicitly
        original = _original_text_by_box(data)
        # Per page index: spans to remove (redaction) and spans to rewrite after.
        rewrites: list[tuple[int, fitz.Rect, str, float, tuple[float, float, float]]] = []
        touched: set[int] = set()

        for node in doc.nodes.values():
            if node.type != "run" or node.bbox is None:
                continue
            pno = _page_number_of(doc, node.id)
            if pno is None or not (1 <= pno <= pdf.page_count):
                continue
            page_index = pno - 1
            b = node.bbox
            rect = fitz.Rect(b.x0, b.y0, b.x1, b.y1)
            page = pdf[page_index]

            if is_redacted(doc, node.id):
                page.add_redact_annot(rect, fill=(0, 0, 0))  # true removal
                touched.add(page_index)
                continue

            current = getattr(node, "text", "")
            if original.get(_box_key(pno, b)) == current:
                continue  # unchanged — leave the original span untouched

            # Edited span: clear the original glyphs (white fill) and queue a rewrite.
            page.add_redact_annot(rect, fill=(1, 1, 1))
            touched.add(page_index)
            size = float(getattr(node, "size", None) or max(rect.height * 0.8, 6.0))
            color = _hex_to_rgb(getattr(node, "color", None))
            rewrites.append((page_index, rect, current, size, color))

        for index in touched:
            pdf[index].apply_redactions()

        for page_index, rect, text, size, color in rewrites:
            page = pdf[page_index]
            # Grow the box downward so slightly larger replacement text still fits.
            box = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + rect.height * 2)
            overflow = page.insert_textbox(box, text, fontsize=size, fontname="helv", color=color)
            if overflow < 0:  # didn't fit — fall back to baseline insert, shrinking as needed
                page.insert_text(rect.bl, text, fontsize=min(size, rect.height), color=color)

        return pdf.tobytes()
    finally:
        pdf.close()
