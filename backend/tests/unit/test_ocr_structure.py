"""OCR structure extraction: positioned, confidence-scored word runs (skips without an engine)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from docos.services.docengine.adapters.image import ocr_available
from docos.services.ocr.tesseract import TesseractOcr


def _text_image() -> bytes:
    img = Image.new("RGB", (320, 80), "white")
    ImageDraw.Draw(img).text((10, 25), "HELLO WORLD", fill="black")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_cleanup_returns_png_without_an_engine():
    # cleanup is pure Pillow — works regardless of Tesseract availability.
    out = TesseractOcr().cleanup(_text_image())
    assert Image.open(io.BytesIO(out)).format == "PNG"


def test_recognize_is_empty_without_engine_or_returns_positioned_runs():
    runs = TesseractOcr().recognize(_text_image())
    if not ocr_available():
        assert runs == []  # degrades cleanly when no engine is present
        return
    assert runs, "expected recognised words when an OCR engine is available"
    for run in runs:
        assert run.bbox is not None  # positioned
        assert "confidence" in run.attrs  # confidence-scored
        assert "ocr_review" in run.attrs  # low-confidence review flag present


def test_infer_reading_order_sorts_top_to_bottom_left_to_right():
    from docos.model.geometry import BBox
    from docos.model.nodes import RunNode

    a = RunNode(id="a", text="x", bbox=BBox(x0=10, y0=0, x1=20, y1=10))  # top-left
    b = RunNode(id="b", text="y", bbox=BBox(x0=0, y0=100, x1=10, y1=110))  # next row
    c = RunNode(id="c", text="z", bbox=BBox(x0=200, y0=0, x1=210, y1=10))  # top-right
    order = TesseractOcr().infer_reading_order([b, c, a])
    assert order == ["a", "c", "b"]
