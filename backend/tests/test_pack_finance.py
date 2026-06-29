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
    inv = _doc(
        "Commercial Invoice",
        "Invoice number: INV-9",
        "PO Number: PO-MISSING",
        "Total due: 5.00 USD",
    )
    report = check_ap([("d1", "inv", inv)])
    assert any(f.code == "po_not_found" for f in report.findings)


def test_ap_endpoint_owner_scoped(client):
    inv = client.post(
        "/documents",
        files={
            "file": (
                "inv.txt",
                b"Commercial Invoice\nInvoice number: E-1\nTotal due: 9.00 USD",
                "text/plain",
            )
        },
    ).json()["doc_id"]
    res = client.post("/packs/finance/ap-check", json={"doc_ids": [inv]})
    assert res.status_code == 200
    assert res.json()["document_count"] == 1


def _upload(client, name, text):
    return client.post("/documents", files={"file": (name, text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_finance_report_generates_downloadable_xlsx(client):
    inv = _upload(
        client,
        "inv.txt",
        "Commercial Invoice\nInvoice number: R-1\nPO Number: PO-3\nTotal due: 200.00 USD",
    )
    po = _upload(client, "po.txt", "Purchase Order\nPO Number: PO-3\nTotal due: 150.00 USD")
    res = client.post("/packs/finance/report?format=xlsx", json={"doc_ids": [inv, po]})
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    assert res.headers["content-disposition"].endswith('finance_report.xlsx"')
    assert res.content[:2] == b"PK"  # a real xlsx (zip) container


def test_finance_report_pdf_and_errors(client):
    inv = _upload(client, "inv.txt", "Commercial Invoice\nInvoice number: R-2\nTotal due: 9.00 USD")
    pdf = client.post("/packs/finance/report?format=pdf", json={"doc_ids": [inv]})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    assert client.post("/packs/finance/report?format=xlsx", json={"doc_ids": []}).status_code == 422
    assert client.post("/packs/nope/report", json={"doc_ids": [inv]}).status_code == 404
    assert (
        client.post("/packs/finance/report?format=exe", json={"doc_ids": [inv]}).status_code == 422
    )
