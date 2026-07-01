"""Expert vertical tests — AP, contracts, HR, insurance cited-findings behavior.

Each vertical proves the same guarantees as the import_export flagship: correct verdict,
cited evidence for positive findings, and honest human-review escalation for absences.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import PageNode, ParagraphNode, RootNode, RunNode
from docos.services.expert.verticals import ap, contracts, hr, insurance


def _doc(doc_id: str, lines: list[str]) -> CanonicalDocument:
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
    now = datetime.now(UTC)
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


# ── AP ────────────────────────────────────────────────────────────────────────


def test_ap_total_mismatch_is_blocked_and_cited():
    inv = _doc("inv", ["Invoice No: INV-1", "Total: USD 10,000.00"])
    po = _doc("po", ["Purchase Order", "PO No: PO-1", "Total: USD 9,000.00"])
    r = ap.audit("p", [("inv", "Inv", inv), ("po", "PO", po)])
    assert r.verdict == "blocked"
    mismatch = [f for f in r.findings if f.type == "field_mismatch"]
    assert mismatch and mismatch[0].evidence
    assert {e.document_id for e in mismatch[0].evidence} == {"inv", "po"}


def test_ap_duplicate_invoice_is_blocked_and_cited():
    inv1 = _doc("a", ["Invoice No: DUP-1", "Total: USD 1,000.00"])
    inv2 = _doc("b", ["Invoice No: DUP-1", "Total: USD 2,000.00"])
    r = ap.audit("p", [("a", "Inv", inv1), ("b", "Inv", inv2)])
    dup = [f for f in r.findings if f.rule_code == "duplicate_invoice"]
    assert dup and dup[0].severity == "blocking"
    assert len(dup[0].evidence) == 2  # both invoices cited


def test_ap_clean_packet_needs_review_no_po():
    """Invoice present, no PO → missing-PO warning (human review), not blocked."""
    inv = _doc("inv", ["Invoice No: INV-9", "Total: USD 5,000.00"])
    r = ap.audit("p", [("inv", "Inv", inv)])
    assert r.verdict == "needs_review"
    assert not [f for f in r.findings if f.severity == "blocking"]


# ── Contracts ─────────────────────────────────────────────────────────────────


def test_contracts_missing_governing_law_escalates_to_human():
    c = _doc("c", ["This Agreement between Alpha and Beta", "The parties hereby agree."])
    r = contracts.audit("p", [("c", "Contract", c)])
    gov = [f for f in r.findings if f.rule_code == "governing_law_missing"]
    assert gov
    assert gov[0].human_review_required is True  # absence → no citation → human


def test_contracts_auto_renew_is_cited():
    c = _doc(
        "c",
        [
            "This Agreement is governed by the laws of Delaware.",
            "This contract shall automatically renew for successive one-year terms.",
        ],
    )
    r = contracts.audit("p", [("c", "Contract", c)])
    renew = [f for f in r.findings if f.rule_code == "auto_renewal"]
    assert renew and renew[0].evidence  # the auto-renew span is cited


# ── HR ────────────────────────────────────────────────────────────────────────


def test_hr_missing_offer_letter_is_blocked():
    r = hr.audit("p", [])
    assert r.verdict == "blocked"
    assert any("Offer" in f.title for f in r.findings)


def test_hr_offer_with_comp_and_start_is_ready():
    offer = _doc(
        "off",
        [
            "Offer Letter",
            "Position of Senior Engineer starting on June 1, 2026.",
            "Annual base salary $120,000.00.",
        ],
    )
    i9 = _doc("i9", ["Form I-9 Employment Eligibility"])
    w4 = _doc("w4", ["Form W-4 Withholding"])
    nda = _doc("nda", ["Confidentiality Agreement"])
    r = hr.audit(
        "p",
        [("off", "Offer", offer), ("i9", "I9", i9), ("w4", "W4", w4), ("nda", "NDA", nda)],
    )
    assert r.verdict == "ready", r.executive_summary


# ── Insurance ─────────────────────────────────────────────────────────────────


def test_insurance_expired_policy_is_blocked_and_cited():
    pol = _doc(
        "pol",
        [
            "Policy No: POL-7",
            "Coverage limit $1,000,000.00",
            "Effective date: 2020-01-01",
            "Expiration date: 2020-12-31",
        ],
    )
    r = insurance.audit("p", [("pol", "Policy", pol)])
    expired = [f for f in r.findings if f.rule_code == "expired_policy"]
    assert expired and expired[0].severity == "blocking"
    assert expired[0].evidence  # the expiration span is cited


def test_insurance_claim_outside_coverage_is_blocked_and_triple_cited():
    past = (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%d")
    pol = _doc(
        "pol",
        [
            "Policy No: POL-8",
            "Coverage limit $500,000.00",
            "Effective date: 2020-01-01",
            "Expiration date: 2021-12-31",
        ],
    )
    claim = _doc("cl", ["Claim No: CL-1", f"Date of loss: {past}"])
    r = insurance.audit("p", [("pol", "Policy", pol), ("cl", "Claim", claim)])
    outside = [f for f in r.findings if f.rule_code == "claim_outside_coverage"]
    assert outside and outside[0].severity == "blocking"
    # Loss date + effective + expiration all cited.
    assert len(outside[0].evidence) >= 3
