"""End-to-end: one-shot Clean Before You Send — fixes applied, verdict flips, proof holds."""

from __future__ import annotations

import io

import fitz


def _upload(client, text: str) -> str:
    return client.post(
        "/documents", files={"file": ("d.txt", text.encode(), "text/plain")}
    ).json()["doc_id"]


def test_clean_redacts_pii_and_proves_unrecoverable(client):
    doc_id = _upload(
        client,
        "Email jane@example.com here.\n\nSSN 123-45-6789.\n\nKeep this line.",
    )

    # Before: the X-ray flags exposed PII.
    assert client.get(f"/documents/{doc_id}/readiness").json()["report"]["verdict"] == "needs_fixes"

    body = client.post(f"/documents/{doc_id}/clean").json()
    assert body["applied"] is True
    assert body["new_version_id"]
    # After: ready, and the proof says the redacted items are unrecoverable.
    assert body["report"]["verdict"] == "ready"
    assert body["validation"]["ok"] is True
    recovery = next(f for f in body["validation"]["findings"] if f["code"] == "redaction.recovery")
    assert recovery["level"] == "pass"

    # The exported clean copy really has the secrets gone but keeps untouched content.
    out = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert out.headers["X-DocOS-Validation"] == "pass"
    text = out.content.decode()
    assert "jane@example.com" not in text
    assert "123-45-6789" not in text
    assert "Keep this line." in text


def test_clean_strips_pdf_metadata(client, sample_pdf_bytes):
    # The sample PDF carries author="Tester" embedded metadata that travels with the file.
    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]
    assert client.get(f"/documents/{doc_id}/readiness").json()["report"]["verdict"] == "needs_fixes"

    assert client.post(f"/documents/{doc_id}/clean").json()["applied"] is True

    out = client.get(f"/documents/{doc_id}/export", params={"format": "pdf"})
    pdf = fitz.open(stream=out.content, filetype="pdf")
    try:
        meta = pdf.metadata or {}
    finally:
        pdf.close()
    assert not meta.get("author")  # embedded author metadata is gone
    assert not meta.get("title")


def test_clean_is_noop_on_a_clean_document(client):
    doc_id = _upload(client, "A perfectly ordinary memo.")
    body = client.post(f"/documents/{doc_id}/clean").json()
    assert body["applied"] is False
    assert body["new_version_id"] is None
    assert body["report"]["verdict"] == "ready"
    assert body["validation"]["ok"] is True
