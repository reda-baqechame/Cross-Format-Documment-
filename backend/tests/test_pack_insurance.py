"""Insurance pack — deterministic policy/claims review."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.packs import check_insurance


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


def _active_policy() -> CanonicalDocument:
    return _doc(
        "Insurance Policy Declarations",
        "Policy Number: POL-12345",
        "Coverage Limit: $1,000,000",
        "Premium: $2,400.00",
        "Deductible: $500.00",
        "Effective Date: 2026-01-01",
        "Expiration Date: 2027-01-01",
    )


def test_extracts_declarations_fields():
    report = check_insurance([("d1", "policy", _active_policy())])
    f = report.documents[0]
    assert f.kind == "policy"
    assert f.policy_number == "POL-12345"
    assert f.coverage_limit == 1000000.0
    assert f.premium == 2400.0
    assert f.deductible == 500.0
    assert f.expiration_date == "2027-01-01"


def test_active_policy_has_no_blocking_issues():
    report = check_insurance([("d1", "policy", _active_policy())])
    assert not any(x.severity == "error" for x in report.findings)


def test_expired_policy_is_flagged():
    expired = _doc(
        "Insurance Policy Declarations",
        "Policy Number: POL-OLD",
        "Coverage Limit: $500,000",
        "Effective Date: 2019-01-01",
        "Expiration Date: 2020-01-01",
    )
    report = check_insurance([("d1", "policy", expired)])
    assert any(x.code == "policy_expired" and x.severity == "error" for x in report.findings)


def test_missing_coverage_limit_flagged():
    doc = _doc(
        "Insurance Policy Declarations",
        "Policy Number: POL-NOCOV",
        "Premium: $300.00",
        "Expiration Date: 2099-01-01",
    )
    report = check_insurance([("d1", "policy", doc)])
    assert any(x.code == "coverage_limit_missing" for x in report.findings)


def test_claim_outside_coverage_period_flagged():
    policy = _doc(
        "Insurance Policy Declarations",
        "Policy Number: POL-CLAIM",
        "Coverage Limit: $250,000",
        "Effective Date: 2026-01-01",
        "Expiration Date: 2026-12-31",
    )
    claim = _doc(
        "Insurance Claim Form",
        "Claim Number: CLM-777",
        "Policy Number: POL-CLAIM",
        "Date of Loss: 2027-03-15",
    )
    report = check_insurance([("d1", "p", policy), ("d2", "c", claim)])
    assert any(
        x.code == "claim_outside_coverage" and x.severity == "error" for x in report.findings
    )


def test_claim_within_coverage_period_ok():
    policy = _doc(
        "Insurance Policy Declarations",
        "Policy Number: POL-OK",
        "Coverage Limit: $250,000",
        "Effective Date: 2026-01-01",
        "Expiration Date: 2026-12-31",
    )
    claim = _doc(
        "Insurance Claim Form",
        "Claim Number: CLM-1",
        "Policy Number: POL-OK",
        "Date of Loss: 2026-06-15",
    )
    report = check_insurance([("d1", "p", policy), ("d2", "c", claim)])
    assert not any(x.code == "claim_outside_coverage" for x in report.findings)


def test_insurance_endpoint_owner_scoped(client):
    body = (
        b"Insurance Policy Declarations\nPolicy Number: POL-E2E\n"
        b"Coverage Limit: $100,000\nExpiration Date: 2099-01-01\n"
    )
    doc_id = client.post(
        "/documents",
        files={"file": ("policy.txt", body, "text/plain")},
    ).json()["doc_id"]
    res = client.post("/packs/insurance/check", json={"doc_ids": [doc_id]})
    assert res.status_code == 200
    assert res.json()["document_count"] == 1
