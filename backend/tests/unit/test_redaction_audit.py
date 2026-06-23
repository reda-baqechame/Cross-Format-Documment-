"""Un-Redact Test: black-box-over-text is detected as recoverable; a clean page is safe."""

from __future__ import annotations

import fitz

from docos.services.provenance import redaction_audit


def _pdf(draw_blackout: bool) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 100), "TopSecret salary 100000 USD", fontsize=12)
    if draw_blackout:
        # The classic failed redaction: an opaque black rectangle drawn over the text,
        # while the glyphs remain in the content stream.
        page.draw_rect(fitz.Rect(60, 86, 360, 104), color=(0, 0, 0), fill=(0, 0, 0))
    data = pdf.tobytes()
    pdf.close()
    return data


def test_blackout_box_over_text_is_flagged_recoverable():
    report = redaction_audit.audit_pdf(_pdf(draw_blackout=True))
    assert report.is_pdf is True
    assert report.covered_regions >= 1
    assert report.recoverable_count >= 1
    assert report.verdict == "leaky"
    # The summary must never echo the recovered text.
    assert "salary" not in report.summary.lower()
    assert "TopSecret" not in report.summary


def test_page_without_covers_is_safe():
    report = redaction_audit.audit_pdf(_pdf(draw_blackout=False))
    assert report.is_pdf is True
    assert report.recoverable_count == 0
    assert report.verdict == "safe"


def test_non_pdf_bytes_are_not_applicable():
    report = redaction_audit.audit_pdf(b"this is not a pdf")
    assert report.is_pdf is False
    assert report.verdict == "not_applicable"
