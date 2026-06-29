"""PDF write-back fidelity: edited text keeps the original family/weight, and round-trips."""

from __future__ import annotations

from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.writers.pdf_writer import _base14_font, write_back_pdf


class _Run:
    def __init__(self, font=None, bold=False, italic=False):
        self.font = font
        self.bold = bold
        self.italic = italic


def test_base14_font_maps_family_and_style():
    assert _base14_font(_Run()) == "helv"
    assert _base14_font(_Run(bold=True)) == "hebo"
    assert _base14_font(_Run(italic=True)) == "heit"
    assert _base14_font(_Run(bold=True, italic=True)) == "hebi"
    # Family inferred from the embedded font name…
    assert _base14_font(_Run(font="Times New Roman")) == "tiro"
    assert _base14_font(_Run(font="TimesNewRoman-Bold")) == "tibo"
    assert _base14_font(_Run(font="CourierNew")) == "cour"
    assert _base14_font(_Run(font="Consolas", bold=True)) == "cobo"
    # …and from style words in the name even without explicit flags.
    assert _base14_font(_Run(font="Arial-BoldItalic")) == "hebi"


def _make_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.insert_text((50, 100), "Original text here", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_edit_round_trips_through_writeback():
    pdf = _make_pdf()
    doc = PdfAdapter().parse(pdf)
    # Edit the first run's text.
    run = next(n for n in doc.nodes.values() if n.type == "run" and getattr(n, "text", ""))
    run.text = "Replaced text now"

    out = write_back_pdf(pdf, doc)
    assert out[:4] == b"%PDF"

    # Re-parse the produced PDF — the new text is present, the old is gone.
    reparsed = PdfAdapter().parse(out)
    text = " ".join(getattr(n, "text", "") for n in reparsed.nodes.values() if n.type == "run")
    assert "Replaced text now" in text
    assert "Original text here" not in text
