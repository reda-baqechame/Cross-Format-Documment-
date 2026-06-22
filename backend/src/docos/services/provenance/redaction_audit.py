"""Un-Redact Test — detect text that *looks* redacted but is still recoverable.

The classic failed redaction is a black rectangle drawn over text (or an unapplied redaction
annotation): the glyphs stay in the content stream, so anyone — or any AI — can select and
extract them in seconds. This scans a PDF's raw bytes for that exact failure mode: text spans
sitting under an opaque dark fill or a redaction annotation, still extractable. It reports how
many are recoverable **without ever echoing the recovered text**.

Pure, deterministic, offline. This is the engine behind the viral "drop your redacted PDF and
see what leaks" demonstration — and the proof point for "ours can't be un-redacted."
"""

from __future__ import annotations

from pydantic import BaseModel

# A fill counts as a "blackout" cover when every channel is this dark or darker.
_DARK_CHANNEL_MAX = 0.30
# A span is considered hidden when this fraction of its area sits under a cover.
_COVER_OVERLAP = 0.6


class RedactionAuditReport(BaseModel):
    """Result of an un-redact test. ``recoverable_count`` never comes with the raw text."""

    is_pdf: bool
    scanned_pages: int = 0
    covered_regions: int = 0  # black-box / redaction covers found
    recoverable_count: int = 0  # text spans hidden under a cover but still extractable
    verdict: str = "not_applicable"  # "safe" | "leaky" | "not_applicable"
    summary: str = ""


def _is_dark(fill) -> bool:
    """True if a drawing fill colour is opaque black-ish (a blackout box)."""
    if not fill:
        return False
    try:
        return all(channel <= _DARK_CHANNEL_MAX for channel in fill)
    except TypeError:
        return False


def _cover_rects(page) -> list:
    """Dark filled rectangles + redaction annotations on a page — the 'looks redacted' marks."""
    import fitz

    covers: list = []
    try:
        for drawing in page.get_drawings():
            if _is_dark(drawing.get("fill")):
                rect = drawing.get("rect")
                if rect is not None:
                    covers.append(fitz.Rect(rect))
    except Exception:  # noqa: BLE001 - a malformed drawing list shouldn't abort the audit
        pass
    try:
        annot = page.first_annot
        while annot is not None:
            # type is (int, "Name"); a redaction annot keeps the covered text until applied.
            if (annot.type[1] or "").lower() == "redact":
                covers.append(fitz.Rect(annot.rect))
            annot = annot.next
    except Exception:  # noqa: BLE001 - annotation iteration is best-effort
        pass
    return covers


def _covered(span_rect, covers) -> bool:
    span_area = abs(span_rect.get_area())
    if span_area <= 0:
        return False
    for cover in covers:
        inter = span_rect & cover
        if not inter.is_empty and abs(inter.get_area()) >= _COVER_OVERLAP * span_area:
            return True
    return False


def audit_pdf(data: bytes) -> RedactionAuditReport:
    """Scan a PDF for text that is visually covered but still recoverable."""
    import fitz

    try:
        pdf = fitz.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001 - a file that won't open as PDF isn't applicable
        return RedactionAuditReport(is_pdf=False, summary="Not a readable PDF.")

    covered_regions = 0
    recoverable = 0
    try:
        for page in pdf:
            covers = _cover_rects(page)
            covered_regions += len(covers)
            if not covers:
                continue
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text") or "").strip()
                        if not text:
                            continue
                        if _covered(fitz.Rect(span.get("bbox")), covers):
                            recoverable += 1
        scanned = pdf.page_count
    finally:
        pdf.close()

    if recoverable:
        verdict = "leaky"
        summary = (
            f"{recoverable} piece(s) of text are hidden under a black box or redaction mark but "
            "still fully recoverable — anyone you send this to can read them in seconds."
        )
    else:
        verdict = "safe"
        summary = (
            "No recoverable text found under any cover. "
            f"Scanned {scanned} page(s) and {covered_regions} covered region(s)."
        )
    return RedactionAuditReport(
        is_pdf=True,
        scanned_pages=scanned,
        covered_regions=covered_regions,
        recoverable_count=recoverable,
        verdict=verdict,
        summary=summary,
    )
