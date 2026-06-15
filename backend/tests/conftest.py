"""Shared fixtures: a sample DOCX built on the fly so tests need no binary blobs."""

from __future__ import annotations

import io

import pytest


@pytest.fixture
def sample_txt_bytes() -> bytes:
    return b"Title line\n\nSecond paragraph with some text.\n\nThird paragraph."


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    import fitz

    pdf = fitz.open()
    pdf.set_metadata({"title": "PDF Test", "author": "Tester"})
    page = pdf.new_page(width=595, height=842)  # A4
    page.insert_text((72, 72), "Hello PDF world", fontsize=14)
    page.insert_text((72, 120), "Second line of text", fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


@pytest.fixture
def sample_docx_bytes() -> bytes:
    from docx import Document

    doc = Document()
    doc.core_properties.title = "Test Doc"
    doc.core_properties.author = "Tester"
    doc.add_heading("A Heading", level=1)
    doc.add_paragraph("A normal paragraph with text.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "r0c0"
    table.cell(1, 1).text = "r1c1"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
