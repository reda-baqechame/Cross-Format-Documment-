"""Document-health computation reflects accessibility and metadata risk."""

from __future__ import annotations

from docos.services.docengine.adapters.docx import DocxAdapter
from docos.services.provenance.health import compute_health


def test_metadata_risk_flagged_for_docx_with_author(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    health = compute_health(doc)
    # author = "Tester" is present and not sanitized
    assert health.metadata_risk is True
    assert any(f.code == "trust.metadata" for f in health.findings)


def test_sanitized_metadata_clears_risk(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    doc.redaction.metadata_sanitized = True
    health = compute_health(doc)
    assert health.metadata_risk is False


def test_accessibility_score_between_zero_and_one(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    health = compute_health(doc)
    assert 0.0 <= health.accessibility_score <= 1.0
