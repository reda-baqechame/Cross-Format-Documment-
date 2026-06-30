"""Expert spine end-to-end tests — the flagship import/export vertical.

These prove the spine works as a whole: cited extraction → fact graph → rules → report,
with the determinism guarantees that make it auditor-grade:

  * a mismatched-total packet yields a BLOCKED verdict and a cited field_mismatch finding;
  * a clean packet yields a READY verdict;
  * every blocking/warning finding carries at least one EvidenceRef (no unfounded claims);
  * the rule builder refuses to construct an uncited blocking finding without escalation.

The synthetic docs are built from the canonical node graph directly so the test is offline
and deterministic with no file I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import PageNode, ParagraphNode, RootNode, RunNode
from docos.services.expert import verticals
from docos.services.expert.rules import new_finding
from docos.services.expert.schemas import ExpertFinding


def _doc(doc_id: str, lines: list[str]) -> CanonicalDocument:
    """Build a one-page canonical doc whose text is the given lines (each its own paragraph)."""
    root = RootNode(id=f"{doc_id}_root", children=[f"{doc_id}_p1"])
    page = PageNode(id=f"{doc_id}_p1", parent_id=root.id, page_number=1, width=612, height=792)
    nodes = {root.id: root, page.id: page}
    for i, line in enumerate(lines):
        para_id = f"{doc_id}_para{i}"
        run_id = f"{doc_id}_run{i}"
        para = ParagraphNode(id=para_id, parent_id=page.id)
        run = RunNode(id=run_id, parent_id=para_id, text=line)
        para.children = [run_id]
        page.children.append(para_id)
        nodes[para_id] = para
        nodes[run_id] = run
    now = datetime.now(tz=UTC)
    return CanonicalDocument(
        doc_id=doc_id,
        root_id=root.id,
        nodes=nodes,
        meta=DocumentMeta(
            title=doc_id,
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )


def _cited(f: ExpertFinding) -> bool:
    return len(f.evidence) > 0


def test_mismatched_totals_blocked_with_citations():
    invoice = _doc(
        "inv1",
        [
            "Commercial Invoice",
            "Invoice No: INV-100",
            "Country of Origin: Morocco",
            "HS Code: 6109100010",
            "Total: CAD 14,920.00",
        ],
    )
    po = _doc(
        "po1",
        [
            "Purchase Order",
            "PO No: PO-555",
            "Total: CAD 13,780.00",
        ],
    )
    report = verticals.import_export.audit(
        "pkt1", [("inv1", "Invoice", invoice), ("po1", "PO", po)]
    )

    assert report.verdict == "blocked"
    mismatch = [f for f in report.findings if f.type == "field_mismatch"]
    assert mismatch, "expected a total mismatch finding"
    assert _cited(mismatch[0]), "total mismatch must cite its evidence"
    # Both docs should be cited in the mismatch evidence.
    cited_docs = {ev.document_id for ev in mismatch[0].evidence}
    assert cited_docs == {"inv1", "po1"}
    assert mismatch[0].severity == "blocking"
    assert mismatch[0].recommended_action  # always actionable


def test_clean_packet_is_ready():
    invoice = _doc(
        "inv2",
        [
            "Commercial Invoice",
            "Invoice No: INV-200",
            "Country of Origin: Morocco",
            "HS Code: 6109100010",
            "Total: CAD 10,000.00",
        ],
    )
    po = _doc(
        "po2",
        ["Purchase Order", "PO No: PO-200", "Total: CAD 10,000.00"],
    )
    bl = _doc(
        "bl2",
        ["Bill of Lading", "B/L No: BL-200", "Gross Weight: 1240 KGS"],
    )
    packing = _doc(
        "pl2",
        ["Packing List", "Gross Weight: 1240 KGS", "No. of Packages: 12"],
    )
    cert = _doc(
        "co2",
        ["Certificate of Origin", "Country of Origin: Morocco"],
    )
    report = verticals.import_export.audit(
        "pkt2",
        [
            ("inv2", "Invoice", invoice),
            ("po2", "PO", po),
            ("bl2", "BL", bl),
            ("pl2", "PL", packing),
            ("co2", "Cert", cert),
        ],
    )
    # No mismatches; totals agree; weights agree; origin + HS present; all required docs present.
    assert report.verdict == "ready", report.executive_summary
    blocking = [f for f in report.findings if f.severity == "blocking"]
    assert blocking == []


def test_packet_missing_optional_doc_is_needs_review():
    """A packet missing an info-severity required doc escalates to human review, not ready."""
    invoice = _doc(
        "inv2b",
        [
            "Commercial Invoice",
            "Country of Origin: Morocco",
            "HS Code: 6109100010",
            "Total: CAD 10,000.00",
        ],
    )
    packing = _doc("pl2b", ["Packing List", "Gross Weight: 1240 KGS"])
    bl = _doc("bl2b", ["Bill of Lading", "Gross Weight: 1240 KGS"])
    report = verticals.import_export.audit(
        "pkt2b",
        [("inv2b", "Invoice", invoice), ("pl2b", "PL", packing), ("bl2b", "BL", bl)],
    )
    # cert-of-origin (info severity) is absent → human_review → needs_review (honest).
    assert report.verdict == "needs_review"
    assert not [f for f in report.findings if f.severity == "blocking"]


def test_evidence_refs_carry_page_and_node():
    invoice = _doc(
        "inv3",
        ["Commercial Invoice", "Country of Origin: Spain", "HS Code: 6109100010"],
    )
    report = verticals.import_export.audit("pkt3", [("inv3", "Invoice", invoice)])
    origin_fields = [f for f in report.extracted_fields if f.name.endswith("origin_country")]
    assert origin_fields
    ref = origin_fields[0].evidence
    assert ref.raw_text  # verbatim source
    assert ref.document_id == "inv3"
    assert ref.page_number == 1


def test_rule_builder_refuses_uncited_blocking_finding():
    """An unfounded blocking claim without human-review escalation must be rejected."""
    import pytest

    with pytest.raises(ValueError):
        new_finding(
            type_="field_mismatch",
            severity="blocking",
            title="x",
            explanation="y",
            evidence=[],
            human_review_required=False,
        )


def test_missing_origin_is_human_review_not_unfounded():
    """Absence findings have no positive evidence, so they escalate to human review."""
    invoice = _doc("inv4", ["Commercial Invoice", "HS Code: 6109100010"])
    report = verticals.import_export.audit("pkt4", [("inv4", "Invoice", invoice)])
    origin = [f for f in report.findings if f.rule_code == "origin_missing"]
    assert origin
    # An uncited warning is only allowed because it explicitly escalates to a human.
    assert origin[0].human_review_required is True
