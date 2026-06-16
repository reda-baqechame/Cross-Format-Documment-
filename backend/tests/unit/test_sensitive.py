"""Sensitive-data detection: precision, masking, and node-level redaction mapping."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.provenance import sensitive


def _doc_with_runs(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    doc = CanonicalDocument(
        doc_id="d1",
        root_id=root.id,
        meta=DocumentMeta(source_format="txt", source_mime="text/plain", created_at=now,
                          modified_at=now, page_count=1),
    )
    doc.add_node(root)
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        doc.add_node(para)
        doc.add_node(run)
    return doc


def test_detects_email_ssn_and_phone():
    doc = _doc_with_runs(["Reach me at jane.doe@example.com or 415-555-2671.", "SSN 123-45-6789"])
    cats = {f.category for f in sensitive.scan_document(doc)}
    assert {"email", "phone", "us_ssn"} <= cats


def test_credit_card_luhn_precision():
    # 4111 1111 1111 1111 is a valid Luhn test card; the second number fails Luhn.
    doc = _doc_with_runs(["Card 4111 1111 1111 1111", "Not a card 1234 5678 9012 3456"])
    cards = [f for f in sensitive.scan_document(doc) if f.category == "credit_card"]
    assert len(cards) == 1
    assert cards[0].node_id == "r0"


def test_excerpt_is_masked_not_raw():
    doc = _doc_with_runs(["SSN 123-45-6789"])
    finding = next(f for f in sensitive.scan_document(doc) if f.category == "us_ssn")
    assert "123-45-6789" not in finding.excerpt
    assert finding.excerpt.endswith("6789")  # last 4 revealed
    assert "•" in finding.excerpt


def test_clean_text_has_no_findings():
    doc = _doc_with_runs(["Just an ordinary sentence with no secrets."])
    assert sensitive.scan_document(doc) == []


def test_redaction_node_ids_deduped_in_order():
    doc = _doc_with_runs(["a@b.com and c@d.com", "e@f.com"])
    ids = sensitive.redaction_node_ids(sensitive.scan_document(doc))
    assert ids == ["r0", "r1"]  # r0 deduped despite two emails


def test_already_redacted_nodes_are_skipped():
    doc = _doc_with_runs(["secret@example.com"])
    doc.redaction.redacted_node_ids.append("r0")
    assert sensitive.scan_document(doc) == []
