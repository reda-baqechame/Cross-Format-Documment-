"""Finance / AP pack — deterministic invoice↔PO matching + duplicate detection."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.packs import check_ap


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


def test_invoice_matches_po_when_consistent():
    inv = _doc(
        "Commercial Invoice", "Invoice number: INV-1", "PO Number: PO-9", "Total due: 100.00 USD"
    )
    po = _doc("Purchase Order", "PO Number: PO-9", "Total due: 100.00 USD")
    report = check_ap([("d1", "inv", inv), ("d2", "po", po)])
    assert report.matches[0].matched_po_doc_id == "d2"
    assert report.matches[0].total_matches is True
    assert not any(f.severity == "error" for f in report.findings)


def test_total_mismatch_is_flagged():
    inv = _doc(
        "Commercial Invoice", "Invoice number: INV-2", "PO Number: PO-7", "Total due: 200.00 USD"
    )
    po = _doc("Purchase Order", "PO Number: PO-7", "Total due: 150.00 USD")
    report = check_ap([("d1", "inv", inv), ("d2", "po", po)])
    assert any(f.code == "po_total_mismatch" for f in report.findings)


def test_duplicate_invoice_number_is_flagged():
    a = _doc("Commercial Invoice", "Invoice number: DUP-1", "Total due: 10.00 USD")
    b = _doc("Commercial Invoice", "Invoice number: DUP-1", "Total due: 10.00 USD")
    report = check_ap([("d1", "a", a), ("d2", "b", b)])
    assert any(f.code == "duplicate_invoice" and f.severity == "error" for f in report.findings)


def test_po_not_found_when_referenced_po_absent():
    inv = _doc("Commercial Invoice", "Invoice number: INV-9", "PO Number: PO-MISSING",
               "Total due: 5.00 USD")
    report = check_ap([("d1", "inv", inv)])
    assert any(f.code == "po_not_found" for f in report.findings)


def test_ap_endpoint_owner_scoped(client):
    inv = client.post(
        "/documents",
        files={"file": ("inv.txt", b"Commercial Invoice\nInvoice number: E-1\nTotal due: 9.00 USD",
                        "text/plain")},
    ).json()["doc_id"]
    res = client.post("/packs/finance/ap-check", json={"doc_ids": [inv]})
    assert res.status_code == 200
    assert res.json()["document_count"] == 1
