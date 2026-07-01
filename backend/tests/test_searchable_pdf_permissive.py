"""Permissive (reportlab, non-AGPL) searchable-PDF writer — verified with pypdfium2, not fitz.

Proves the permissive engine produces genuinely selectable text and honors redaction (true removal
carries through), so it can replace the PyMuPDF path behind ``PDF_ENGINE=permissive``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.docengine.writers.searchable_pdf import model_to_searchable_pdf
from docos.settings import get_settings


@pytest.fixture
def permissive_engine(monkeypatch):
    monkeypatch.setenv("PDF_ENGINE", "permissive")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _pdfium_text(data: bytes) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    return "\n".join(pdf.get_page(i).get_textpage().get_text_range() for i in range(len(pdf)))


def _doc(*paragraphs: str) -> tuple[CanonicalDocument, dict[str, str]]:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    run_ids: dict[str, str] = {}
    for i, text in enumerate(paragraphs):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=text)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
        run_ids[text] = r.id
    return doc, run_ids


def test_permissive_born_digital_is_selectable(permissive_engine):
    doc, _ = _doc("Searchable heading", "A body paragraph with real words.")
    data = model_to_searchable_pdf(doc)
    assert data[:5] == b"%PDF-"
    text = _pdfium_text(data)
    assert "Searchable heading" in text
    assert "body paragraph" in text


def test_permissive_honors_redaction(permissive_engine):
    doc, run_ids = _doc("Public line here", "SECRET-TOKEN-XYZ confidential")
    doc.redaction.redacted_node_ids = [run_ids["SECRET-TOKEN-XYZ confidential"]]
    text = _pdfium_text(model_to_searchable_pdf(doc))
    assert "Public line" in text
    assert "SECRET-TOKEN-XYZ" not in text  # true removal carries into the searchable PDF


def test_permissive_engine_produces_no_fitz_dependency(permissive_engine):
    # The permissive path must not import fitz. Build a PDF and confirm reportlab produced it
    # (reportlab stamps its Producer); this guards against silent fallback to the AGPL engine.
    doc, _ = _doc("Engine provenance check")
    data = model_to_searchable_pdf(doc)
    assert b"ReportLab" in data
