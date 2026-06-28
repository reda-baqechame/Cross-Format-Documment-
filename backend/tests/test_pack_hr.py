"""HR / onboarding pack — offer extraction + onboarding-packet completeness."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.packs import check_onboarding


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


def _offer() -> CanonicalDocument:
    return _doc(
        "Offer Letter",
        "We are pleased to offer you the position of Senior Engineer at Acme Corp.",
        "Your start date will be March 1, 2026.",
        "Your annual base salary will be $150,000.",
        "This is a full-time, at-will employment relationship.",
    )


def test_extracts_offer_terms():
    report = check_onboarding([("d1", "offer", _offer())])
    o = report.offers[0]
    assert o.role == "Senior Engineer"
    assert o.start_date == "March 1, 2026"
    assert o.compensation == "$150,000"
    assert o.employment_type == "full-time"
    assert o.at_will is True


def test_complete_packet_has_no_gaps():
    docs = [
        ("d1", "offer", _offer()),
        ("d2", "i9", _doc("Form I-9", "Employment Eligibility Verification")),
        ("d3", "w4", _doc("Form W-4", "Employee Withholding Certificate")),
        ("d4", "nda", _doc("Confidentiality Agreement", "Proprietary and non-disclosure.")),
    ]
    report = check_onboarding(docs)
    assert all(item.present for item in report.checklist)
    assert not any(f.severity == "warn" for f in report.findings)


def test_missing_documents_flagged():
    report = check_onboarding([("d1", "offer", _offer())])
    codes = [f.code for f in report.findings]
    assert codes.count("document_missing") == 3  # i-9, w-4, nda absent


def test_offer_missing_terms_flagged():
    bare = _doc("Offer Letter", "We are pleased to offer you a role.")
    report = check_onboarding([("d1", "offer", bare)])
    codes = {f.code for f in report.findings}
    assert "start_date_missing" in codes
    assert "compensation_missing" in codes


def test_onboarding_endpoint_owner_scoped(client):
    body = b"Offer Letter\nWe are pleased to offer you the position of Analyst.\n"
    doc_id = client.post(
        "/documents",
        files={"file": ("offer.txt", body, "text/plain")},
    ).json()["doc_id"]
    res = client.post("/packs/hr/onboarding-check", json={"doc_ids": [doc_id]})
    assert res.status_code == 200
    assert res.json()["document_count"] == 1
