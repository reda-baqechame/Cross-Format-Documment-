"""End-to-end vertical slice: upload → canonical model → health, on a SQLite db.

Uses an in-process SQLite database (no Postgres needed) by overriding the session
dependency, so the whole route pipeline is exercised in CI.
"""

from __future__ import annotations

import io

from docos.db.models import Document, JobRecord


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["privacy_mode"] in {"offline", "enterprise", "cloud"}
    # AI state is reported so the UI never shows a silently-failing AI feature.
    assert body["ai_enabled"] is False  # default config is the offline noop provider
    assert body["llm_provider"] == "noop"


def test_upload_txt_then_fetch_model_and_health(client):
    files = {"file": ("note.txt", b"Hello world\n\nSecond block.", "text/plain")}
    up = client.post("/documents", files=files)
    assert up.status_code == 200, up.text
    doc_id = up.json()["doc_id"]

    model = client.get(f"/documents/{doc_id}/model")
    assert model.status_code == 200
    document = model.json()["document"]
    assert document["meta"]["source_format"] == "txt"
    assert any(n["type"] == "run" for n in document["nodes"].values())

    health = client.get(f"/documents/{doc_id}/health")
    assert health.status_code == 200
    assert "accessibility_score" in health.json()["health"]


def test_upload_docx(client, sample_docx_bytes):
    files = {
        "file": (
            "doc.docx",
            io.BytesIO(sample_docx_bytes),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    up = client.post("/documents", files=files)
    assert up.status_code == 200, up.text
    doc_id = up.json()["doc_id"]
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert any(n["type"] == "heading" for n in model["nodes"].values())


def test_upload_pdf(client, sample_pdf_bytes):
    files = {"file": ("doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    up = client.post("/documents", files=files)
    assert up.status_code == 200, up.text
    doc_id = up.json()["doc_id"]
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["meta"]["source_format"] == "pdf"
    assert any(n["type"] == "page" for n in model["nodes"].values())
    runs = [n for n in model["nodes"].values() if n["type"] == "run"]
    assert any("Hello PDF world" in n["text"] for n in runs)


def test_malformed_magic_matched_file_is_rejected_before_blob_stage(client, db, tmp_path):
    files = {"file": ("bad.pdf", b"%PDF-1.7\nnot really a pdf", "application/pdf")}
    resp = client.post("/documents", files=files)
    assert resp.status_code == 422, resp.text
    assert db.query(Document).count() == 0
    failed = db.query(JobRecord).filter(JobRecord.kind == "ingest").all()
    assert failed and failed[-1].status == "failed"
    blob_root = tmp_path / "blobs"
    assert not blob_root.exists() or not any(blob_root.rglob("*"))


def test_patch_endpoint_noop(client):
    files = {"file": ("note.txt", b"editable text", "text/plain")}
    doc_id = client.post("/documents", files=files).json()["doc_id"]
    resp = client.post(f"/documents/{doc_id}/patches", json={"instruction": "make it formal"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False  # noop client generates no ops
    assert body["intent"] == "make it formal"
