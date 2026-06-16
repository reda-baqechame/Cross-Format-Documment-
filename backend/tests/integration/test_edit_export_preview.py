"""End-to-end: explicit edits, export, preview, sanitize, and redaction.

Exercises the full mutate → version → export loop over the route pipeline on a
SQLite database, reusing the ``client`` fixture from ``test_upload_to_model``.
"""

from __future__ import annotations

import io

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload_txt(client, body: bytes = b"editable text\n\nsecond block") -> str:
    files = {"file": ("note.txt", body, "text/plain")}
    return client.post("/documents", files=files).json()["doc_id"]


def _first_run_id(client, doc_id: str) -> str:
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    return next(n["id"] for n in model["nodes"].values() if n["type"] == "run")


def test_explicit_set_text_edit_persists_and_versions(client):
    doc_id = _upload_txt(client)
    run_id = _first_run_id(client, doc_id)

    resp = client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "rewritten"}}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied"] is True

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["nodes"][run_id]["text"] == "rewritten"

    history = client.get(f"/documents/{doc_id}/history").json()["versions"]
    assert len(history) >= 2  # ingest + edit


def test_explicit_op_with_bad_target_is_rejected(client):
    doc_id = _upload_txt(client)
    resp = client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": "nope", "payload": {"text": "x"}}]},
    )
    assert resp.status_code == 422


def test_patch_request_requires_instruction_or_ops(client):
    doc_id = _upload_txt(client)
    resp = client.post(f"/documents/{doc_id}/patches", json={})
    assert resp.status_code == 422


def test_export_txt_and_docx(client):
    doc_id = _upload_txt(client, b"Hello export")

    txt = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert txt.status_code == 200
    assert "attachment" in txt.headers["content-disposition"]
    assert b"Hello export" in txt.content

    docx = client.get(f"/documents/{doc_id}/export", params={"format": "docx"})
    assert docx.status_code == 200
    assert docx.headers["content-type"] == _DOCX_MIME
    assert docx.content[:2] == b"PK"  # docx is a zip


def test_unknown_export_format_is_400(client):
    doc_id = _upload_txt(client)
    resp = client.get(f"/documents/{doc_id}/export", params={"format": "rtf"})
    assert resp.status_code == 400


def test_pdf_origin_exports_as_docx(client, sample_pdf_bytes):
    files = {"file": ("doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    doc_id = client.post("/documents", files=files).json()["doc_id"]

    docx = client.get(f"/documents/{doc_id}/export", params={"format": "docx"})
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"


def test_preview_pdf_returns_png(client, sample_pdf_bytes):
    files = {"file": ("doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    doc_id = client.post("/documents", files=files).json()["doc_id"]

    resp = client.get(f"/documents/{doc_id}/preview", params={"page": 0})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_non_pdf_is_400(client):
    doc_id = _upload_txt(client)
    resp = client.get(f"/documents/{doc_id}/preview", params={"page": 0})
    assert resp.status_code == 400


def test_sanitize_metadata_endpoint_flips_health(client, sample_docx_bytes):
    files = {"file": ("doc.docx", io.BytesIO(sample_docx_bytes), _DOCX_MIME)}
    doc_id = client.post("/documents", files=files).json()["doc_id"]

    assert client.get(f"/documents/{doc_id}/health").json()["health"]["metadata_risk"] is True

    resp = client.post(f"/documents/{doc_id}/sanitize-metadata")
    assert resp.status_code == 200, resp.text

    assert client.get(f"/documents/{doc_id}/health").json()["health"]["metadata_risk"] is False


def test_redact_then_export_omits_text(client):
    doc_id = _upload_txt(client, b"keep me\n\nSECRET token")
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    secret_id = next(
        n["id"] for n in model["nodes"].values() if n["type"] == "run" and "SECRET" in n["text"]
    )

    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "redact", "target_id": secret_id}]},
    )

    txt = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert b"SECRET token" not in txt.content
    assert b"keep me" in txt.content
