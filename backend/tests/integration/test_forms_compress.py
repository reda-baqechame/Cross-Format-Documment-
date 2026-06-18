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


def test_form_builder_detect_create_update_delete(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("form.txt", b"Name: ______\nEmail: ______", "text/plain")},
    ).json()["doc_id"]

    detected = client.post(f"/documents/{doc_id}/fields/detect")
    assert detected.status_code == 200
    assert detected.json()["detected"] == 2
    fields = client.get(f"/documents/{doc_id}/fields").json()["fields"]
    assert {f["field_name"] for f in fields} == {"Name", "Email"}
    assert all(f["required"] for f in fields)

    created = client.post(
        f"/documents/{doc_id}/fields/create",
        json={"field_name": "Signature", "field_kind": "signature", "required": True},
    )
    assert created.status_code == 200 and created.json()["applied"] is True
    signature = next(
        f for f in client.get(f"/documents/{doc_id}/fields").json()["fields"]
        if f["field_name"] == "Signature"
    )

    updated = client.patch(
        f"/documents/{doc_id}/fields/{signature['node_id']}",
        json={"field_name": "Applicant signature", "field_kind": "signature"},
    )
    assert updated.status_code == 200 and updated.json()["applied"] is True
    assert any(
        f["field_name"] == "Applicant signature"
        for f in client.get(f"/documents/{doc_id}/fields").json()["fields"]
    )

    deleted = client.delete(f"/documents/{doc_id}/fields/{signature['node_id']}")
    assert deleted.status_code == 200 and deleted.json()["applied"] is True
    assert all(
        f["node_id"] != signature["node_id"]
        for f in client.get(f"/documents/{doc_id}/fields").json()["fields"]
    )


def test_asset_upload_accepts_images_only(client, sample_image_bytes):
    doc_id = client.post("/documents", files={"file": ("d.txt", b"x", "text/plain")}).json()[
        "doc_id"
    ]
    ok = client.post(
        f"/documents/{doc_id}/assets",
        files={"file": ("asset.png", io.BytesIO(sample_image_bytes), "image/png")},
    )
    assert ok.status_code == 200
    assert ok.json()["blob_ref"].startswith(f"assets/{doc_id}/")

    bad = client.post(
        f"/documents/{doc_id}/assets",
        files={"file": ("asset.txt", b"nope", "text/plain")},
    )
    assert bad.status_code == 415
