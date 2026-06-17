"""Universal canonical-model → XLSX / PPTX / PNG writers."""

from __future__ import annotations

import io

from openpyxl import load_workbook
from PIL import Image
from pptx import Presentation

from docos.services.docengine.adapters.docx import DocxAdapter
from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.docengine.adapters.xlsx import XlsxAdapter
from docos.services.docengine.writers.image_writer import model_to_png
from docos.services.docengine.writers.pptx_writer import model_to_pptx
from docos.services.docengine.writers.xlsx_writer import model_to_xlsx


def test_model_to_xlsx_rebuilds_table_from_spreadsheet(sample_xlsx_bytes):
    doc = XlsxAdapter().parse(sample_xlsx_bytes)
    wb = load_workbook(io.BytesIO(model_to_xlsx(doc)))
    values = {
        str(cell.value)
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for cell in row
        if cell.value is not None
    }
    assert {"Region", "Total", "North", "1200"}.issubset(values)


def test_model_to_xlsx_puts_loose_text_on_a_sheet():
    doc = TxtAdapter().parse(b"First line\n\nSecond line")
    wb = load_workbook(io.BytesIO(model_to_xlsx(doc)))
    text = {str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row}
    assert "First line" in text and "Second line" in text


def test_model_to_xlsx_always_has_a_sheet():
    doc = TxtAdapter().parse(b"")
    wb = load_workbook(io.BytesIO(model_to_xlsx(doc)))
    assert len(wb.worksheets) >= 1


def test_model_to_pptx_one_slide_per_page(sample_pptx_bytes):
    from docos.services.docengine.adapters.pptx import PptxAdapter

    doc = PptxAdapter().parse(sample_pptx_bytes)
    prs = Presentation(io.BytesIO(model_to_pptx(doc)))
    assert len(prs.slides) >= 1
    all_text = " ".join(
        run.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
        for para in shape.text_frame.paragraphs
        for run in para.runs
    )
    assert "Slide Title" in all_text


def test_model_to_pptx_sections_flat_doc_by_heading(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    prs = Presentation(io.BytesIO(model_to_pptx(doc)))
    text = " ".join(
        run.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
        for para in shape.text_frame.paragraphs
        for run in para.runs
    )
    assert "A Heading" in text and "normal paragraph" in text


def test_model_to_png_is_a_valid_image():
    doc = TxtAdapter().parse(b"Hello image world\n\nA second paragraph here.")
    png = model_to_png(doc)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.width > 0 and img.height > 0
