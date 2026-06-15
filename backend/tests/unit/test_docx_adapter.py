"""DOCX adapter extracts headings, paragraphs, tables, and metadata."""

from __future__ import annotations

from docos.services.docengine.adapters.docx import DocxAdapter


def test_extracts_heading_and_metadata(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    assert doc.meta.title == "Test Doc"
    headings = [n for n in doc.nodes.values() if n.type == "heading"]
    assert headings and headings[0].level == 1
    assert "H1" in headings[0].tags


def test_extracts_table(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    tables = [n for n in doc.nodes.values() if n.type == "table"]
    cells = [n for n in doc.nodes.values() if n.type == "table_cell"]
    assert tables and tables[0].rows == 2 and tables[0].cols == 2
    assert len(cells) == 4


def test_title_sets_accessibility_flag(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    assert doc.accessibility.has_doc_title is True
