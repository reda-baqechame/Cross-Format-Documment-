"""Pack-extraction accuracy eval (deterministic, offline, no model calls).

Builds labeled invoice / PO / shipment documents with known fields and runs the Finance (AP) and
Import/Export packs over them, scoring (1) field-extraction accuracy against the labels and (2)
finding correctness (the right issues are raised: total mismatch, duplicate invoice, missing docs).
Exits non-zero if accuracy drops below the gate, so the verticals' real-world accuracy is a CI gate,
not a claim.

Run from the repo root:  ``python evals/pack_extraction/run_local.py``
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.ids import new_doc_id, new_node_id  # noqa: E402
from docos.model.nodes import ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.packs import check_ap, check_packet  # noqa: E402

GATE = 1.0  # deterministic extraction must be exact on the labeled set.


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


def _field_checks() -> list[tuple[str, bool]]:
    """Per-field extraction accuracy against known labels."""
    inv = _doc(
        "Commercial Invoice",
        "Invoice number: INV-100",
        "PO Number: PO-55",
        "Total due: 1200.00 USD",
    )
    rep = check_ap([("inv", "invoice", inv)])
    f = rep.documents[0]
    return [
        ("invoice_number", f.invoice_number == "INV-100"),
        ("po_number", f.po_number == "PO-55"),
        ("total", f.total == 1200.0),
        ("currency", f.currency == "USD"),
    ]


def _finding_checks() -> list[tuple[str, bool]]:
    """The packs must raise the right issues on known-bad inputs (and stay clean on good ones)."""
    inv = _doc(
        "Commercial Invoice", "Invoice number: INV-1", "PO Number: PO-9", "Total due: 200 USD"
    )
    po = _doc("Purchase Order", "PO Number: PO-9", "Total due: 150 USD")
    mismatch = check_ap([("d1", "inv", inv), ("d2", "po", po)])

    dup_a = _doc("Commercial Invoice", "Invoice number: DUP-1", "Total due: 10 USD")
    dup_b = _doc("Commercial Invoice", "Invoice number: DUP-1", "Total due: 10 USD")
    dup = check_ap([("d1", "a", dup_a), ("d2", "b", dup_b)])

    ci = _doc(
        "Commercial Invoice", "Total due: 100 EUR", "Country of origin: Germany", "HS code 123456"
    )
    partial = check_packet([("d1", "ci", ci)])

    return [
        ("ap_total_mismatch", any(x.code == "po_total_mismatch" for x in mismatch.findings)),
        ("ap_duplicate_invoice", any(x.code == "duplicate_invoice" for x in dup.findings)),
        ("packet_missing_docs", any(x.code == "document_missing" for x in partial.findings)),
        ("packet_origin_present", not any(x.code == "origin_missing" for x in partial.findings)),
    ]


def main() -> int:
    checks = _field_checks() + _finding_checks()
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    rate = passed / total if total else 1.0

    print(json.dumps({name: ok for name, ok in checks}, indent=2))
    for name, ok in checks:
        print(f"  [{'ok ' if ok else 'FAIL'}] {name}")
    print(f"Pack-extraction accuracy: {passed}/{total} = {rate:.0%} (gate {GATE:.0%})")

    if rate < GATE:
        print("GATE FAILED")
        return 1
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
