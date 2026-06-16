"""End-to-end PDF page-ops endpoints (rotate/delete/reorder/extract/merge)."""

from __future__ import annotations

import io

import fitz


def _multipage_pdf(labels: list[str]) -> bytes:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page(width=300, height=300)
        page.insert_text((50, 50), label, fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


def _upload_pdf(client, labels: list[str]) -> str:
    return client.post(
        "/documents",
        files={"file": ("d.pdf", io.BytesIO(_multipage_pdf(labels)), "application/pdf")},
    ).json()["doc_id"]


def _page_texts(content: bytes) -> list[str]:
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        return [p.get_text().strip() for p in doc]
    finally:
        doc.close()


def test_delete_and_reorder_endpoints(client):
    doc_id = _upload_pdf(client, ["A", "B", "C"])

    out = client.post(f"/documents/{doc_id}/pages/delete", json={"pages": [1]})
    assert out.status_code == 200
    assert _page_texts(out.content) == ["A", "C"]

    out = client.post(f"/documents/{doc_id}/pages/reorder", json={"order": [2, 1, 0]})
    assert _page_texts(out.content) == ["C", "B", "A"]


def test_extract_endpoint(client):
    doc_id = _upload_pdf(client, ["A", "B", "C", "D"])
    out = client.get(f"/documents/{doc_id}/pages/extract", params={"pages": "0,3"})
    assert out.status_code == 200
    assert _page_texts(out.content) == ["A", "D"]


def test_merge_endpoint(client):
    a = _upload_pdf(client, ["A1", "A2"])
    b = _upload_pdf(client, ["B1"])
    out = client.post(f"/documents/{a}/merge", json={"doc_ids": [b]})
    assert out.status_code == 200
    assert _page_texts(out.content) == ["A1", "A2", "B1"]


def test_page_ops_reject_non_pdf(client):
    doc_id = client.post(
        "/documents", files={"file": ("n.txt", b"hi", "text/plain")}
    ).json()["doc_id"]
    assert client.post(f"/documents/{doc_id}/pages/delete", json={"pages": [0]}).status_code == 400


def test_out_of_range_returns_422(client):
    doc_id = _upload_pdf(client, ["A"])
    assert client.post(f"/documents/{doc_id}/pages/delete", json={"pages": [9]}).status_code == 422
