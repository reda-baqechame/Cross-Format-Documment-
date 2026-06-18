"""Validation engine over the API: report endpoint, download headers, isolation."""

from __future__ import annotations

import fitz


def _upload(client, data: bytes) -> str:
    res = client.post("/documents", files={"file": ("d.pdf", data, "application/pdf")})
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def test_export_report_pdf_ok(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)
    res = client.get(f"/documents/{doc_id}/export/report", params={"format": "pdf"})
    assert res.status_code == 200
    report = res.json()["validation"]
    assert report["ok"] is True
    codes = {f["code"] for f in report["findings"]}
    assert {"output.opens", "pages.count"} <= codes


def test_export_download_carries_validation_header(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)
    res = client.get(f"/documents/{doc_id}/export", params={"format": "docx"})
    assert res.status_code == 200
    assert res.headers.get("X-DocOS-Validation") in ("pass", "warn", "fail")
    assert res.headers.get("X-DocOS-Validation-Summary")


def test_redact_then_export_report_is_unrecoverable(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    run_id = next(
        nid
        for nid, n in model["nodes"].items()
        if n.get("type") == "run" and "Hello" in (n.get("text") or "")
    )
    patched = client.post(
        f"/documents/{doc_id}/patches", json={"ops": [{"op": "redact", "target_id": run_id}]}
    )
    assert patched.status_code == 200, patched.text

    report = client.get(f"/documents/{doc_id}/export/report", params={"format": "pdf"}).json()[
        "validation"
    ]
    assert report["ok"] is True
    assert any(
        f["code"] == "redaction.recovery" and f["level"] == "pass" for f in report["findings"]
    )

    # And the real download genuinely no longer contains the redacted text.
    out = client.get(f"/documents/{doc_id}/export", params={"format": "pdf"}).content
    text = "\n".join(p.get_text() for p in fitz.open(stream=out, filetype="pdf"))
    assert "Hello" not in text


def test_pageop_response_has_validation_header(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)
    res = client.post(f"/documents/{doc_id}/watermark", json={"text": "DRAFT"})
    assert res.status_code == 200
    assert res.headers.get("X-DocOS-Validation") == "pass"


def test_export_report_is_owner_scoped(make_client, sample_pdf_bytes):
    alice = make_client()
    bob = make_client()
    doc_id = _upload(alice, sample_pdf_bytes)
    assert (
        bob.get(f"/documents/{doc_id}/export/report", params={"format": "pdf"}).status_code == 404
    )
