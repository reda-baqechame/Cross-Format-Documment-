"""Contracts / CLM pack — deterministic clause extraction + risk review."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.packs import check_contracts


def _doc(*lines: str) -> CanonicalDocument:
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
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


_FULL = (
    "SERVICES AGREEMENT",
    "This Agreement is made between Acme Corp and Beta LLC, effective as of January 1, 2026.",
    "The term of this Agreement shall be for a period of two (2) years.",
    "This Agreement shall automatically renew for successive one-year terms.",
    "Either party may terminate upon thirty (30) days written notice.",
    "In no event shall liability exceed the fees paid. Limitation of liability applies.",
    "Payment terms are Net 30.",
    "This Agreement shall be governed by the laws of the State of Delaware.",
)


def test_extracts_key_terms_from_full_contract():
    report = check_contracts([("d1", "agreement", _doc(*_FULL))])
    f = report.documents[0]
    assert f.parties == ["Acme Corp", "Beta LLC"]
    assert f.governing_law == "Delaware"
    assert f.auto_renew is True
    assert f.termination_notice_days == 30
    assert f.has_liability_cap is True
    assert f.payment_terms == "Net 30"


def test_clean_contract_has_no_warnings():
    # A complete contract with no auto-renewal — auto-renewal is itself a (legitimate) warning.
    clean = (
        "SERVICES AGREEMENT",
        "This Agreement is made between Acme Corp and Beta LLC, effective as of January 1, 2026.",
        "The term of this Agreement shall be for a period of two (2) years.",
        "Either party may terminate upon thirty (30) days written notice.",
        "In no event shall liability exceed the fees paid. Limitation of liability applies.",
        "This Agreement shall be governed by the laws of the State of Delaware.",
    )
    report = check_contracts([("d1", "agreement", _doc(*clean))])
    assert not any(x.severity == "warn" for x in report.findings)


def test_bare_document_flags_missing_clauses():
    report = check_contracts([("d1", "memo", _doc("Memo", "Hello world."))])
    codes = {x.code for x in report.findings}
    assert "governing_law_missing" in codes
    assert "termination_notice_missing" in codes
    assert "liability_cap_missing" in codes


def test_auto_renewal_is_flagged():
    doc = _doc(
        "This Agreement shall automatically renew for successive one-year terms.",
        "Governed by the laws of California. Either party may terminate on 60 days notice.",
        "Liability shall not exceed the total fees.",
    )
    report = check_contracts([("d1", "c", doc)])
    assert any(x.code == "auto_renewal" for x in report.findings)


def test_contracts_endpoint_owner_scoped(client):
    body = b"Master Agreement\nGoverned by the laws of New York.\n"
    doc_id = client.post(
        "/documents",
        files={"file": ("c.txt", body, "text/plain")},
    ).json()["doc_id"]
    res = client.post("/packs/contracts/check", json={"doc_ids": [doc_id]})
    assert res.status_code == 200
    assert res.json()["document_count"] == 1
