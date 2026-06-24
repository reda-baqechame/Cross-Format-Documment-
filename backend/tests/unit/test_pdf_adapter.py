"""PDF adapter extracts pages, text runs with bbox/metadata, and renders previews."""

from __future__ import annotations

from docos.services.docengine.adapters.pdf import PdfAdapter


def test_parses_pages_and_metadata(sample_pdf_bytes):
    doc = PdfAdapter().parse(sample_pdf_bytes)
    assert doc.meta.source_format == "pdf"
    assert doc.meta.title == "PDF Test"
    assert doc.meta.page_count == 1

    pages = [n for n in doc.nodes.values() if n.type == "page"]
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert round(pages[0].width) == 595 and round(pages[0].height) == 842


def test_extracts_text_runs_with_bbox(sample_pdf_bytes):
    doc = PdfAdapter().parse(sample_pdf_bytes)
    runs = [n for n in doc.nodes.values() if n.type == "run"]
    text = " ".join(r.text for r in runs)
    assert "Hello PDF world" in text
    assert "Second line of text" in text
    # Geometry is preserved for fidelity.
    assert all(r.bbox is not None for r in runs)


def test_title_sets_accessibility_flag(sample_pdf_bytes):
    doc = PdfAdapter().parse(sample_pdf_bytes)
    assert doc.accessibility.has_doc_title is True


def test_render_preview_returns_png(sample_pdf_bytes):
    png = PdfAdapter().render_preview_bytes(sample_pdf_bytes, 0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_rasterize_pages_batch(sample_pdf_bytes):
    adapter = PdfAdapter()
    pages = adapter.rasterize_pages(sample_pdf_bytes, [0, 0, 0], max_pages=1)
    assert set(pages) == {0}
    assert pages[0][:8] == b"\x89PNG\r\n\x1a\n"
