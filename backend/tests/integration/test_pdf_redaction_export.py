"""PDF write-back: redacted text is truly removed from the exported PDF."""

from __future__ import annotations

import io

import fitz


def test_pdf_export_burns_in_redactions(client, sample_pdf_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    secret = next(
        n["id"]
        for n in model["nodes"].values()
        if n["type"] == "run" and "Hello PDF world" in n["text"]
    )
    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "redact", "target_id": secret}]},
    )

    out = client.get(f"/documents/{doc_id}/export", params={"format": "pdf"})
    assert out.status_code == 200
    assert out.headers["content-type"] == "application/pdf"

    pdf = fitz.open(stream=out.content, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in pdf)
    finally:
        pdf.close()
    assert "Hello PDF world" not in text  # truly removed
    assert "Second line of text" in text  # untouched content survives


def test_pdf_export_writes_back_edited_text(client, sample_pdf_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    target = next(
        n["id"]
        for n in model["nodes"].values()
        if n["type"] == "run" and "Hello PDF world" in n["text"]
    )
    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": target, "payload": {"text": "Edited head"}}]},
    )

    out = client.get(f"/documents/{doc_id}/export", params={"format": "pdf"})
    assert out.status_code == 200
    pdf = fitz.open(stream=out.content, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in pdf)
    finally:
        pdf.close()
    assert "Edited head" in text  # the edit was written back
    assert "Hello PDF world" not in text  # original glyphs were cleared
    assert "Second line of text" in text  # untouched span preserved verbatim


def test_pdf_export_rejected_for_non_pdf(client):
    doc_id = client.post("/documents", files={"file": ("n.txt", b"hi", "text/plain")}).json()[
        "doc_id"
    ]
    assert client.get(f"/documents/{doc_id}/export", params={"format": "pdf"}).status_code == 400
