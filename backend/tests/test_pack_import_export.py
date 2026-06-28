"""Import/export business pack — deterministic cross-document packet validation."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.packs import check_packet
from docos.services.packs.import_export import extract_shipment_fields


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


def test_extract_shipment_fields_pulls_currency_total_hs_origin():
    f = extract_shipment_fields(
        "d1",
        "Invoice",
        _doc(
            "Commercial Invoice",
            "Invoice number: INV-1001",
            "Total due: 8,420.00 USD",
            "HS Code: 851713",
            "Country of origin: Morocco",
        ),
    )
    assert f.currency == "USD"
    assert f.total == 8420.00
    assert f.hs_code == "851713"
    assert "Morocco" in (f.origin or "")
    assert f.invoice_number == "INV-1001"


def test_packet_flags_currency_and_total_mismatch():
    inv = _doc("Commercial Invoice", "Total due: 8,420.00 USD", "HS Code: 851713",
               "Country of origin: China")
    po = _doc("Purchase Order", "PO Number: PO-9012", "Total due: 7,900.00 EUR")
    report = check_packet([("d1", "Invoice", inv), ("d2", "PO", po)])
    codes = {f.code for f in report.findings}
    assert "currency_mismatch" in codes
    assert "total_mismatch" in codes
    assert any(f.severity == "error" for f in report.findings)


def test_packet_clean_when_consistent_and_complete_has_no_errors():
    common = ("Total due: 1000.00 USD", "HS Code: 851713", "Country of origin: Morocco")
    docs = [
        ("d1", "Invoice", _doc("Commercial Invoice", *common)),
        ("d2", "Packing list", _doc("Packing List", *common)),
        ("d3", "BOL", _doc("Bill of Lading", "shipper", "consignee", "carrier", *common)),
        ("d4", "COO", _doc("Certificate of Origin", *common)),
    ]
    report = check_packet(docs)
    assert not any(f.severity == "error" for f in report.findings)


def test_packet_checklist_reports_missing_documents():
    report = check_packet([("d1", "Invoice", _doc("Commercial Invoice", "Total due: 5.00 USD"))])
    missing = {c.doc_type for c in report.checklist if not c.present}
    assert "bill_of_lading" in missing
    assert any(f.code == "document_missing" for f in report.findings)


def test_pack_endpoint_owner_scoped(client):
    inv = client.post(
        "/documents",
        files={"file": ("inv.txt", b"Commercial Invoice\nTotal due: 100.00 USD\nHS Code: 851713",
                        "text/plain")},
    ).json()["doc_id"]
    res = client.post("/packs/import-export/check", json={"doc_ids": [inv]})
    assert res.status_code == 200
    body = res.json()
    assert body["document_count"] == 1
    assert "checklist" in body and "findings" in body
