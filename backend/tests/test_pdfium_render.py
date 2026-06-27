"""The permissive pypdfium2 render seam produces PNGs matching the PyMuPDF rasteriser."""

from __future__ import annotations

import io

from PIL import Image

from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.pdfium import pdfium_available

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _size(png: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(png)).size


def test_pdfium_is_installed():
    # pypdfium2 is a core dependency (the permissive PDF render engine), so it must import.
    assert pdfium_available() is True


def test_default_engine_renders_png(sample_pdf_bytes):
    png = PdfAdapter().render_preview_bytes(sample_pdf_bytes, 0)
    assert png.startswith(_PNG_MAGIC)


def test_pdfium_engine_matches_pymupdf(sample_pdf_bytes, monkeypatch):
    from docos.settings import get_settings

    pymupdf_png = PdfAdapter().render_preview_bytes(sample_pdf_bytes, 0)

    monkeypatch.setenv("PDF_RENDER_ENGINE", "pdfium")
    get_settings.cache_clear()
    pdfium_png = PdfAdapter().render_preview_bytes(sample_pdf_bytes, 0)
    get_settings.cache_clear()

    assert pdfium_png.startswith(_PNG_MAGIC)
    # Same page rendered at the same scale → same pixel dimensions (allow 1px rounding).
    w1, h1 = _size(pymupdf_png)
    w2, h2 = _size(pdfium_png)
    assert abs(w1 - w2) <= 1 and abs(h1 - h2) <= 1
