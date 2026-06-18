"""Replacement-grade hardening checks across the high-risk document surfaces."""

from __future__ import annotations

import io
import zipfile

import pytest

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _upload(client, filename: str, data: bytes, mime: str) -> str:
    res = client.post("/documents", files={"file": (filename, io.BytesIO(data), mime)})
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def _first_run_id(client, doc_id: str) -> str:
    doc = client.get(f"/documents/{doc_id}/model").json()["document"]
    return next(node_id for node_id, node in doc["nodes"].items() if node["type"] == "run")


@pytest.mark.stress
def test_all_primary_formats_upload_and_validate_export(
    client,
    sample_pdf_bytes,
    sample_docx_bytes,
    sample_xlsx_bytes,
    sample_pptx_bytes,
    sample_image_bytes,
):
    cases = [
        ("doc.pdf", sample_pdf_bytes, "application/pdf", "pdf", "pdf"),
        ("doc.docx", sample_docx_bytes, _DOCX, "docx", "docx"),
        ("book.xlsx", sample_xlsx_bytes, _XLSX, "xlsx", "xlsx"),
        ("deck.pptx", sample_pptx_bytes, _PPTX, "pptx", "pptx"),
        ("notes.md", b"# Heading\n\nAmount: $123.45", "text/markdown", "md", "md"),
        ("rows.csv", b"Name,Total\nAlice,10\nBob,15", "text/csv", "csv", "csv"),
        ("page.html", b"<h1>Heading</h1><p>Body</p>", "text/html", "html", "html"),
        ("scan.png", sample_image_bytes, "image/png", "image", "png"),
    ]
    for filename, data, mime, source_format, export_format in cases:
        doc_id = _upload(client, filename, data, mime)
        model = client.get(f"/documents/{doc_id}/model").json()["document"]
        assert model["meta"]["source_format"] == source_format
        report = client.get(f"/documents/{doc_id}/export/report", params={"format": export_format})
        assert report.status_code == 200, report.text
        assert "validation" in report.json()


@pytest.mark.stress
def test_malformed_zip_and_declared_oversize_are_rejected(client):
    bad_zip = io.BytesIO()
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("not-office.txt", "not an office package")
    rejected = client.post(
        "/documents",
        files={"file": ("fake.docx", bad_zip.getvalue(), _DOCX)},
    )
    assert rejected.status_code in {415, 501}

    too_large = client.post(
        "/documents",
        headers={"content-length": str(51 * 1024 * 1024)},
        files={"file": ("tiny.txt", b"x", "text/plain")},
    )
    assert too_large.status_code == 413


@pytest.mark.stress
def test_patch_undo_loop_keeps_version_history_coherent(client):
    doc_id = _upload(client, "loop.txt", b"Original text", "text/plain")
    run_id = _first_run_id(client, doc_id)

    for i in range(30):
        patched = client.post(
            f"/documents/{doc_id}/patches",
            json={
                "ops": [
                    {
                        "op": "set_text",
                        "target_id": run_id,
                        "payload": {"text": f"Stress edit {i}"},
                    }
                ]
            },
        )
        assert patched.status_code == 200, patched.text

    history = client.get(f"/documents/{doc_id}/history").json()["versions"]
    assert len(history) >= 31

    for _ in range(30):
        undo = client.post(f"/documents/{doc_id}/undo")
        assert undo.status_code == 200, undo.text

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["nodes"][run_id]["text"] == "Original text"


@pytest.mark.stress
def test_editor_session_lifecycle_is_audited_and_honest(client, sample_docx_bytes):
    doc_id = _upload(client, "office.docx", sample_docx_bytes, _DOCX)
    started = client.post(f"/documents/{doc_id}/editor/session", json={})
    assert started.status_code == 200, started.text
    payload = started.json()
    assert payload["provider"] == "local_basic"
    assert payload["warnings"]
    session_id = payload["session_id"]

    saved = client.post(
        f"/documents/{doc_id}/editor/session/{session_id}/save",
        json={"note": "stress save"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "saved"
    assert saved.json()["saved_version_id"]


@pytest.mark.stress
def test_ops_agent_never_executes_destructive_actions_without_approval(client):
    doc_id = _upload(client, "packet.txt", b"Agreement\nEmail: a@example.com", "text/plain")
    plan = client.post(
        f"/documents/{doc_id}/ops-agent/plan",
        json={"goal": "clean redact approve and export this agreement"},
    )
    assert plan.status_code == 200, plan.text
    payload = plan.json()
    redact = next(action for action in payload["actions"] if action["tool"] == "redact")
    assert redact["destructive"] is True
    assert redact["requires_approval"] is True
    assert any("Destructive actions are planned only" in warning for warning in payload["warnings"])

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["redaction"]["redacted_node_ids"] == []


@pytest.mark.stress
def test_template_variables_include_fields_and_mustache_tokens(client):
    doc_id = _upload(
        client,
        "template.txt",
        b"Hello {{Client Name}}\nSignature: ______",
        "text/plain",
    )
    detect = client.post(f"/documents/{doc_id}/fields/detect")
    assert detect.status_code == 200, detect.text
    saved = client.post(
        f"/documents/{doc_id}/save-as-template",
        json={"name": "Client packet", "description": "Variable-aware template"},
    )
    assert saved.status_code == 200, saved.text
    variables = set(saved.json()["variables"])
    assert "Client Name" in variables
    assert any("Signature" in variable for variable in variables)
