"""End-to-end: the Un-Redact Test endpoint over the FastAPI client."""

from __future__ import annotations

import io

import fitz


def _blackout_pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 100), "Confidential account 4111 1111 1111 1111", fontsize=12)
    page.draw_rect(fitz.Rect(60, 86, 420, 104), color=(0, 0, 0), fill=(0, 0, 0))
    data = pdf.tobytes()
    pdf.close()
    return data


def test_blackout_pdf_audit_reports_leaky(client):
    files = {"file": ("redacted.pdf", io.BytesIO(_blackout_pdf()), "application/pdf")}
    doc_id = client.post("/documents", files=files).json()["doc_id"]

    audit = client.get(f"/documents/{doc_id}/redaction-audit").json()["audit"]
    assert audit["is_pdf"] is True
    assert audit["verdict"] == "leaky"
    assert audit["recoverable_count"] >= 1
    assert "4111" not in audit["summary"]  # never echoes the recovered value


def test_non_pdf_audit_is_not_applicable(client):
    doc_id = client.post(
        "/documents", files={"file": ("d.txt", b"plain text", "text/plain")}
    ).json()["doc_id"]
    audit = client.get(f"/documents/{doc_id}/redaction-audit").json()["audit"]
    assert audit["is_pdf"] is False
    assert audit["verdict"] == "not_applicable"
