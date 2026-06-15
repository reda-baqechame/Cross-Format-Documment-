"""Every functional format ingests and exports to DOCX via the canonical model."""

from __future__ import annotations

import io

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _upload(client, name, data, mime) -> str:
    up = client.post("/documents", files={"file": (name, io.BytesIO(data), mime)})
    assert up.status_code == 200, up.text
    return up.json()["doc_id"]


def test_xlsx_ingests_and_exports_docx(client, sample_xlsx_bytes):
    doc_id = _upload(client, "book.xlsx", sample_xlsx_bytes, _XLSX)
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["meta"]["source_format"] == "xlsx"

    out = client.get(f"/documents/{doc_id}/export", params={"format": "docx"})
    assert out.status_code == 200 and out.content[:2] == b"PK"

    txt = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert b"North" in txt.content


def test_pptx_ingests_and_exports(client, sample_pptx_bytes):
    doc_id = _upload(client, "deck.pptx", sample_pptx_bytes, _PPTX)
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["meta"]["source_format"] == "pptx"
    txt = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert b"Slide Title" in txt.content


def test_rtf_ingests_and_exports(client, sample_rtf_bytes):
    doc_id = _upload(client, "note.rtf", sample_rtf_bytes, "application/rtf")
    txt = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert b"First RTF line" in txt.content


def test_image_ingests_and_previews(client, sample_image_bytes):
    doc_id = _upload(client, "scan.png", sample_image_bytes, "image/png")
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert model["meta"]["source_format"] == "image"
    assert any(n["type"] == "image" for n in model["nodes"].values())

    preview = client.get(f"/documents/{doc_id}/preview", params={"page": 0})
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"
