"""Activatable document-intelligence seams: Docling / PaddleOCR / Tika / QPDF + async job status.

Every engine is an *optional* upgrade that defaults to the built-in behaviour. These tests prove the
fallback contract holds with nothing extra installed (so CI + offline use are unaffected) and that
the async job-status read endpoint works and is owner-scoped.
"""

from __future__ import annotations

import io

from docos.db.models import JobRecord
from docos.services.docengine.registry import default_registry
from docos.services.ocr.tesseract import TesseractOcr


def test_docling_registry_falls_back_to_native(sample_pdf_bytes):
    """With Docling not installed, the docling-engine registry still parses via native adapters."""
    registry = default_registry("docling")
    adapter = registry.resolve("application/pdf")
    doc = adapter.parse(sample_pdf_bytes)
    assert doc.meta.source_format == "pdf"
    # Native parse ran (no docling provenance marker), proving the transparent fallback.
    assert doc.meta.custom.get("parsed_by") != "docling"
    # The registry shape is identical regardless of engine.
    assert registry.resolve_by_format("pdf") is adapter


def test_ocr_factory_defaults_to_tesseract(monkeypatch):
    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    from docos.settings import get_settings

    get_settings.cache_clear()
    from docos.services.ocr.factory import get_ocr_service

    assert isinstance(get_ocr_service(), TesseractOcr)
    get_settings.cache_clear()


def test_ocr_paddle_choice_falls_back_when_unavailable(monkeypatch):
    """OCR_ENGINE=paddle degrades to Tesseract when PaddleOCR isn't installed (the CI case)."""
    monkeypatch.setenv("OCR_ENGINE", "paddle")
    from docos.settings import get_settings

    get_settings.cache_clear()
    from docos.services.ocr import paddle
    from docos.services.ocr.factory import get_ocr_service

    assert paddle.paddle_available() is False
    assert isinstance(get_ocr_service(), TesseractOcr)
    get_settings.cache_clear()


def test_qpdf_is_noop_when_binary_absent(monkeypatch):
    from docos.services.ingestion import qpdf

    monkeypatch.setattr(qpdf.shutil, "which", lambda _name: None)
    data = b"%PDF-1.4 not really a pdf"
    assert qpdf.qpdf_available() is False
    assert qpdf.is_encrypted(data) is False
    assert qpdf.check_ok(data) is True
    assert qpdf.repair_and_linearize(data) == data  # original bytes, untouched


def test_tika_client_detect_and_metadata(monkeypatch):
    from docos.services.ingestion import tika

    class _Resp:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_put(url, **kwargs):
        if url.endswith("/detect/stream"):
            return _Resp(text="application/pdf")
        if url.endswith("/meta"):
            return _Resp(payload={"Author": "Jane", "Content-Type": "application/pdf"})
        return _Resp(text="extracted text")

    monkeypatch.setattr(tika.httpx, "put", fake_put)
    client = tika.TikaClient("http://tika.local")
    assert client.detect_mime(b"bytes") == "application/pdf"
    assert client.metadata(b"bytes")["Author"] == "Jane"
    assert client.extract_text(b"bytes") == "extracted text"


def test_job_status_endpoint_after_upload(client, db):
    files = {"file": ("note.txt", b"Hello world\n\nSecond block.", "text/plain")}
    up = client.post("/documents", files=files)
    assert up.status_code == 200, up.text
    doc_id = up.json()["doc_id"]

    job = db.query(JobRecord).filter(JobRecord.document_id == doc_id).first()
    assert job is not None and job.status == "succeeded"

    resp = client.get(f"/jobs/{job.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == job.id
    assert body["status"] == "succeeded"
    assert body["document_id"] == doc_id
    assert body["finished"] is True


def test_job_status_unknown_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_job_status_is_owner_scoped(make_client, db):
    owner = make_client()
    other = make_client()
    files = {"file": ("note.txt", io.BytesIO(b"private content"), "text/plain")}
    doc_id = owner.post("/documents", files=files).json()["doc_id"]
    job = db.query(JobRecord).filter(JobRecord.document_id == doc_id).first()
    assert job is not None
    # A different session cannot read the owner's job (document ownership is enforced).
    assert other.get(f"/jobs/{job.id}").status_code == 404
    assert owner.get(f"/jobs/{job.id}").status_code == 200
