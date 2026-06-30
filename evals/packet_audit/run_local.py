"""Expert packet-audit eval — the rung-9 (expert_verified) gate.

Runs the evidence-bound expert verticals over golden packet corpora with known expected
verdicts + expected finding codes, and scores:

  1. verdict accuracy  — predicted verdict == expected verdict
  2. critical-finding recall — every expected blocking rule_code is emitted
  3. evidence coverage — every blocking/warning finding carries ≥1 cited EvidenceRef
     (absences are allowed only with human_review_required)
  4. no false blocking — no unexpected blocking finding (precision)

Exits non-zero on any regression, so the verticals' expert-grade quality is a CI gate, not
a claim. This is the difference between ``verified`` (rung 8) and ``expert_verified``
(rung 9) on the capability ladder.

Run from the repo root:  ``python evals/packet_audit/run_local.py``
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.nodes import PageNode, ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.expert.schemas import ExpertReport  # noqa: E402
from docos.services.expert.verticals import ap, contracts, hr, import_export, insurance  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────────────────


def _doc(doc_id: str, lines: list[str]) -> CanonicalDocument:
    root = RootNode(id=f"{doc_id}_root", children=[f"{doc_id}_p1"])
    page = PageNode(
        id=f"{doc_id}_p1", parent_id=root.id, page_number=1, width=612, height=792
    )
    nodes = {root.id: root, page.id: page}
    for i, line in enumerate(lines):
        pid = f"{doc_id}_para{i}"
        rid = f"{doc_id}_run{i}"
        para = ParagraphNode(id=pid, parent_id=page.id)
        run = RunNode(id=rid, parent_id=pid, text=line)
        para.children = [rid]
        page.children.append(pid)
        nodes[pid] = para
        nodes[rid] = run
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


# ── Golden corpora ─────────────────────────────────────────────────────────────
# Each case: vertical, docs, expected verdict, expected blocking rule_codes,
# and (optionally) forbidden blocking rule_codes (precision check).


def _import_export_cases() -> list[dict]:
    return [
        {
            "name": "ie_clean",
            "vertical": import_export,
            "docs": [
                ("inv", "inv", _doc("inv", [
                    "Commercial Invoice", "Invoice No: INV-1",
                    "Country of Origin: Morocco", "HS Code: 6109100010",
                    "Total: CAD 10,000.00",
                ])),
                ("po", "po", _doc("po", ["Purchase Order", "PO No: PO-1", "Total: CAD 10,000.00"])),
                ("bl", "bl", _doc("bl", ["Bill of Lading", "B/L No: BL-1", "Gross Weight: 1240 KGS"])),
                ("pl", "pl", _doc("pl", ["Packing List", "Gross Weight: 1240 KGS", "No. of Packages: 12"])),
                ("co", "co", _doc("co", ["Certificate of Origin", "Country of Origin: Morocco"])),
            ],
            "expected_verdict": "ready",
            "expected_blocking": [],
        },
        {
            "name": "ie_total_mismatch",
            "vertical": import_export,
            "docs": [
                ("inv", "inv", _doc("inv", [
                    "Commercial Invoice", "Country of Origin: Morocco",
                    "HS Code: 6109100010", "Total: CAD 14,920.00",
                ])),
                ("po", "po", _doc("po", ["Purchase Order", "Total: CAD 13,780.00"])),
            ],
            "expected_verdict": "blocked",
            "expected_blocking": ["total_mismatch"],
        },
        {
            "name": "ie_currency_mismatch",
            "vertical": import_export,
            "docs": [
                ("inv", "inv", _doc("inv", ["Commercial Invoice", "Total: USD 1,000.00", "Country of Origin: USA", "HS Code: 6109100010"])),
                ("po", "po", _doc("po", ["Purchase Order", "Total: CAD 1,000.00"])),
            ],
            "expected_verdict": "blocked",
            "expected_blocking": ["currency_mismatch"],
        },
    ]


def _ap_cases() -> list[dict]:
    return [
        {
            "name": "ap_total_mismatch",
            "vertical": ap,
            "docs": [
                ("inv", "inv", _doc("inv", ["Invoice No: INV-9", "Total: USD 10,000.00"])),
                ("po", "po", _doc("po", ["Purchase Order", "PO No: PO-9", "Total: USD 9,000.00"])),
            ],
            "expected_verdict": "blocked",
            "expected_blocking": ["total_mismatch"],
        },
        {
            "name": "ap_duplicate_invoice",
            "vertical": ap,
            "docs": [
                ("a", "a", _doc("a", ["Invoice No: DUP-1", "Total: USD 1,000.00"])),
                ("b", "b", _doc("b", ["Invoice No: DUP-1", "Total: USD 1,000.00"])),
            ],
            "expected_verdict": "blocked",
            "expected_blocking": ["duplicate_invoice"],
        },
        {
            "name": "ap_missing_po",
            "vertical": ap,
            "docs": [("inv", "inv", _doc("inv", ["Invoice No: INV-7", "Total: USD 5,000.00"]))],
            "expected_verdict": "needs_review",  # missing PO is a warning → human review
            "expected_blocking": [],
        },
    ]


def _contracts_cases() -> list[dict]:
    return [
        {
            "name": "contracts_auto_renew",
            "vertical": contracts,
            "docs": [
                ("c", "c", _doc("c", [
                    "This Agreement is governed by the laws of Delaware.",
                    "This contract shall automatically renew for successive one-year terms.",
                ])),
            ],
            "expected_verdict": "needs_review",  # auto-renew is a warning
            "expected_blocking": [],
            "expected_warnings": ["auto_renewal"],
        },
        {
            "name": "contracts_missing_everything",
            "vertical": contracts,
            "docs": [("c", "c", _doc("c", ["This Agreement between Alpha and Beta.", "The parties hereby agree."]))],
            "expected_verdict": "needs_review",  # absences → human review
            "expected_blocking": [],
        },
    ]


def _hr_cases() -> list[dict]:
    return [
        {
            "name": "hr_missing_offer",
            "vertical": hr,
            "docs": [],
            "expected_verdict": "blocked",
            "expected_blocking": ["missing_required_documents"],
        },
        {
            "name": "hr_complete",
            "vertical": hr,
            "docs": [
                ("off", "off", _doc("off", [
                    "Offer Letter", "Position of Engineer starting on June 1, 2026.",
                    "Annual base salary $120,000.00.",
                ])),
                ("i9", "i9", _doc("i9", ["Form I-9 Employment Eligibility"])),
                ("w4", "w4", _doc("w4", ["Form W-4 Withholding"])),
                ("nda", "nda", _doc("nda", ["Confidentiality Agreement"])),
            ],
            "expected_verdict": "ready",
            "expected_blocking": [],
        },
    ]


def _insurance_cases() -> list[dict]:
    return [
        {
            "name": "ins_expired",
            "vertical": insurance,
            "docs": [
                ("pol", "pol", _doc("pol", [
                    "Policy No: POL-1", "Coverage limit $1,000,000.00",
                    "Effective date: 2020-01-01", "Expiration date: 2020-12-31",
                ])),
            ],
            "expected_verdict": "blocked",
            "expected_blocking": ["expired_policy"],
        },
        {
            "name": "ins_active_no_claim",
            "vertical": insurance,
            "docs": [
                ("pol", "pol", _doc("pol", [
                    "Policy No: POL-2", "Coverage limit $500,000.00",
                    "Effective date: 2024-01-01", "Expiration date: 2099-12-31",
                ])),
            ],
            "expected_verdict": "ready",  # complete + active policy, no claim -> clean
            "expected_blocking": [],
        },
    ]


def _all_cases() -> list[dict]:
    return (
        _import_export_cases()
        + _ap_cases()
        + _contracts_cases()
        + _hr_cases()
        + _insurance_cases()
    )


# ── Scoring ────────────────────────────────────────────────────────────────────


def _assert_case(case: dict) -> None:
    report: ExpertReport = case["vertical"].audit(f"eval-{case['name']}", case["docs"])

    # 1. verdict accuracy
    if report.verdict != case["expected_verdict"]:
        raise AssertionError(
            f"{case['name']}: verdict {report.verdict!r} != expected {case['expected_verdict']!r}"
        )

    blocking_codes = {
        f.rule_code for f in report.findings if f.severity == "blocking"
    }

    # 2. critical-finding recall
    for code in case.get("expected_blocking", []):
        if code not in blocking_codes:
            raise AssertionError(
                f"{case['name']}: missing expected blocking finding {code!r}; "
                f"got {sorted(blocking_codes)}"
            )

    # 3. evidence coverage: every blocking/warning finding must be cited OR escalate
    for f in report.findings:
        if f.severity in ("blocking", "warning") and not f.evidence:
            if not f.human_review_required:
                raise AssertionError(
                    f"{case['name']}: {f.severity} finding {f.rule_code!r} has no evidence "
                    "and no human_review_required — unfounded claim."
                )

    # 4. no false blocking (precision): no unexpected blocking codes
    expected_blocking = set(case.get("expected_blocking", []))
    unexpected = blocking_codes - expected_blocking
    if unexpected:
        raise AssertionError(
            f"{case['name']}: unexpected blocking findings {sorted(unexpected)}"
        )

    # 5. expected warnings recall (if declared)
    warning_codes = {f.rule_code for f in report.findings if f.severity == "warning"}
    for code in case.get("expected_warnings", []):
        if code not in warning_codes:
            raise AssertionError(
                f"{case['name']}: missing expected warning {code!r}; got {sorted(warning_codes)}"
            )


def main() -> None:
    cases = _all_cases()
    for case in cases:
        _assert_case(case)
    print(f"packet_audit expert eval passed {len(cases)} cases (verdict + recall + evidence + precision)")


if __name__ == "__main__":
    main()
