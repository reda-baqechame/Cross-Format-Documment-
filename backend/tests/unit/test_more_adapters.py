"""XLSX / PPTX / RTF / image adapters parse into the canonical model."""

from __future__ import annotations

import io

import pytest

from docos.services.docengine.adapters.image import ImageAdapter, ocr_available
from docos.services.docengine.adapters.pptx import PptxAdapter
from docos.services.docengine.adapters.rtf import RtfAdapter
from docos.services.docengine.adapters.xlsx import XlsxAdapter


def _runs(doc) -> list[str]:
    return [n.text for n in doc.nodes.values() if n.type == "run" and n.text]


def test_xlsx_parses_sheet_into_table(sample_xlsx_bytes):
    doc = XlsxAdapter().parse(sample_xlsx_bytes)
    assert doc.meta.source_format == "xlsx"
    assert any(n.type == "table" for n in doc.nodes.values())
    texts = _runs(doc)
    assert "Sales" in texts  # sheet-name heading
    assert "Region" in texts and "North" in texts and "1200" in texts


def test_pptx_parses_slides_into_pages(sample_pptx_bytes):
    doc = PptxAdapter().parse(sample_pptx_bytes)
    assert doc.meta.source_format == "pptx"
    assert any(n.type == "page" for n in doc.nodes.values())
    texts = " ".join(_runs(doc))
    assert "Slide Title" in texts and "slide content" in texts


def test_rtf_parses_lines_into_paragraphs(sample_rtf_bytes):
    doc = RtfAdapter().parse(sample_rtf_bytes)
    assert doc.meta.source_format == "rtf"
    texts = _runs(doc)
    assert "First RTF line" in texts and "Second RTF line" in texts


def test_image_parses_into_image_node(sample_image_bytes):
    doc = ImageAdapter().parse(sample_image_bytes)
    assert doc.meta.source_format == "image"
    images = [n for n in doc.nodes.values() if n.type == "image"]
    assert len(images) == 1
    assert images[0].attrs.get("width") == 120
    assert any(n.type == "page" for n in doc.nodes.values())


@pytest.mark.skipif(not ocr_available(), reason="no Tesseract engine with language data")
def test_image_ocr_recovers_text():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 90), color="white")
    ImageDraw.Draw(img).text((10, 30), "Invoice 2026", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = ImageAdapter().parse(buf.getvalue())
    text = " ".join(n.text for n in doc.nodes.values() if n.type == "run")
    assert "Invoice" in text
