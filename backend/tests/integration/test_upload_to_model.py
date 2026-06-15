"""End-to-end vertical slice: upload → canonical model → health, on a SQLite db.

Uses an in-process SQLite database (no Postgres needed) by overriding the session
dependency, so the whole route pipeline is exercised in CI.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from docos.db.base import Base
from docos.deps import db_session
from docos.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Route blob storage to a temp dir so tests leave no artifacts.
    monkeypatch.setenv("LOCAL_BLOB_DIR", str(tmp_path / "blobs"))
    monkeypatch.setenv(
        "ALLOWED_MIME_TYPES",
        "text/plain,application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    engine = create_engine(f"sqlite:///{tmp_path/'test.db'}", future=True)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app = create_app()
    app.dependency_overrides[db_session] = _session
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["privacy_mode"] in {"offline", "enterprise", "cloud"}


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


def test_patch_endpoint_noop(client):
    files = {"file": ("note.txt", b"editable text", "text/plain")}
    doc_id = client.post("/documents", files=files).json()["doc_id"]
    resp = client.post(f"/documents/{doc_id}/patches", json={"instruction": "make it formal"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False  # noop client generates no ops
    assert body["intent"] == "make it formal"
