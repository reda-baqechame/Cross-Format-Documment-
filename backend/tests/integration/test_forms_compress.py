"""Fillable form fields and PDF compression."""

from __future__ import annotations

import io

import fitz


def test_compress_returns_valid_pdf(client, sample_pdf_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]
    out = client.post(f"/documents/{doc_id}/compress")
    assert out.status_code == 200
    doc = fitz.open(stream=out.content, filetype="pdf")
    try:
        assert doc.page_count == 1
    finally:
        doc.close()


def test_field_listing_and_fill_roundtrip(client):
    # Start from a txt doc, then inject a form field via the add_node patch op.
    doc_id = client.post(
        "/documents", files={"file": ("d.txt", b"form below", "text/plain")}
    ).json()["doc_id"]
    root_id = client.get(f"/documents/{doc_id}/model").json()["document"]["root_id"]

    client.post(
        f"/documents/{doc_id}/patches",
        json={
            "ops": [
                {
                    "op": "add_node",
                    "payload": {
                        "node": {
                            "id": "field-1",
                            "type": "field",
                            "field_name": "Full Name",
                            "field_kind": "text",
                        },
                        "parent_id": root_id,
                    },
                }
            ]
        },
    )

    fields = client.get(f"/documents/{doc_id}/fields").json()["fields"]
    assert any(f["node_id"] == "field-1" and f["field_name"] == "Full Name" for f in fields)

    res = client.post(f"/documents/{doc_id}/fields", json={"node_id": "field-1", "value": "Alice"})
    assert res.status_code == 200 and res.json()["applied"] is True

    after = client.get(f"/documents/{doc_id}/fields").json()["fields"]
    assert next(f for f in after if f["node_id"] == "field-1")["value"] == "Alice"


def test_fill_unknown_field_404(client):
    doc_id = client.post("/documents", files={"file": ("d.txt", b"x", "text/plain")}).json()[
        "doc_id"
    ]
    assert (
        client.post(
            f"/documents/{doc_id}/fields", json={"node_id": "nope", "value": "v"}
        ).status_code
        == 404
    )
