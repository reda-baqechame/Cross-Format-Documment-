"""End-to-end structured-data extraction endpoint."""

from __future__ import annotations


def test_extract_endpoint(client):
    doc_id = client.post(
        "/documents",
        files={
            "file": (
                "inv.txt",
                b"Invoice Number: INV-44\n\nTotal: $1,200.00 due 2026-05-01\n\nbill@acme.com",
                "text/plain",
            )
        },
    ).json()["doc_id"]

    body = client.get(f"/documents/{doc_id}/extract").json()
    types = {e["type"] for e in body["extraction"]["entities"]}
    assert {"money", "date", "email"} <= types
    keys = {f["key"] for f in body["extraction"]["fields"]}
    assert "Invoice Number" in keys
