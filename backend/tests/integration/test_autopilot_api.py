"""Autopilot endpoint: typed result, owner-scoping, offline."""

from __future__ import annotations

INVOICE = (
    "ACME Supplies\n\nInvoice Number: INV-1042\nInvoice Date: 2026-01-15\n"
    "Due Date: 2026-02-15\n\nSubtotal: $1,000.00\nTax: $100.00\nTotal Due: $1,100.00\n"
)


def _upload_txt(client, text: str, name: str = "invoice.txt") -> str:
    res = client.post("/documents", files={"file": (name, text.encode(), "text/plain")})
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def test_autopilot_invoice(client):
    doc_id = _upload_txt(client, INVOICE)
    res = client.get(f"/documents/{doc_id}/autopilot")
    assert res.status_code == 200
    ap = res.json()["autopilot"]
    assert ap["type_id"] == "invoice"
    assert ap["category"] == "Financial"
    assert ap["deep"] is True
    names = {f["name"] for f in ap["fields"]}
    assert {"invoice_number", "total"} <= names
    assert any(a["kind"] == "export" and a["params"].get("format") == "xlsx" for a in ap["actions"])


def test_autopilot_is_owner_scoped(make_client):
    alice = make_client()
    bob = make_client()
    doc_id = _upload_txt(alice, INVOICE)
    assert bob.get(f"/documents/{doc_id}/autopilot").status_code == 404


def test_autopilot_generic_for_plain_text(client):
    doc_id = _upload_txt(client, "Just some notes about the weekend.\n", name="notes.txt")
    ap = client.get(f"/documents/{doc_id}/autopilot").json()["autopilot"]
    assert ap["deep"] is False
    assert isinstance(ap["actions"], list) and ap["actions"]
