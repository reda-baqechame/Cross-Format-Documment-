"""PDF protect (encrypt) + watermark endpoints."""

from __future__ import annotations

import io

import fitz


def _upload_pdf(client, sample_pdf_bytes) -> str:
    return client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]


def test_protect_produces_encrypted_pdf(client, sample_pdf_bytes):
    doc_id = _upload_pdf(client, sample_pdf_bytes)
    out = client.post(f"/documents/{doc_id}/protect", json={"password": "s3cret"})
    assert out.status_code == 200

    doc = fitz.open(stream=out.content, filetype="pdf")
    try:
        assert doc.needs_pass  # locked without the password
        assert doc.authenticate("s3cret")  # opens with it
    finally:
        doc.close()


def test_watermark_text_appears_on_page(client, sample_pdf_bytes):
    doc_id = _upload_pdf(client, sample_pdf_bytes)
    out = client.post(f"/documents/{doc_id}/watermark", json={"text": "CONFIDENTIAL"})
    assert out.status_code == 200

    doc = fitz.open(stream=out.content, filetype="pdf")
    try:
        text = "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()
    assert "CONFIDENTIAL" in text


def test_protect_requires_pdf(client):
    doc_id = client.post(
        "/documents", files={"file": ("n.txt", b"hi", "text/plain")}
    ).json()["doc_id"]
    assert client.post(f"/documents/{doc_id}/protect", json={"password": "x"}).status_code == 400
