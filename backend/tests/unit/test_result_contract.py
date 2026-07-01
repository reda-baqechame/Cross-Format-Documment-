"""ResultContract builder tests."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.expert.readiness_bridge import readiness_to_expert_findings
from docos.services.expert.result_contract import from_readiness
from docos.services.provenance import readiness


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    doc = CanonicalDocument(
        doc_id="d1",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    doc.add_node(root)
    for i, line in enumerate(texts):
        p = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        r = RunNode(id=f"r{i}", parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def test_from_readiness_wraps_findings_and_score():
    doc = _doc(["Email jane@example.com please."])
    report = readiness.build_report(doc)
    findings = readiness_to_expert_findings(doc.doc_id, doc, report)
    result = from_readiness(doc.doc_id, report, findings)
    assert result.job_type == "clean_before_send"
    assert result.verdict == "needs_review"
    assert 0 <= result.score <= 100
    assert result.proof_report_url.endswith("readiness/report?format=html")
    assert result.fix_plans_available >= 1


def test_from_readiness_ready_doc():
    doc = _doc(["A clean memo."])
    report = readiness.build_report(doc)
    findings = readiness_to_expert_findings(doc.doc_id, doc, report)
    result = from_readiness(doc.doc_id, report, findings)
    assert result.verdict == "ready"
    assert result.score == 100
