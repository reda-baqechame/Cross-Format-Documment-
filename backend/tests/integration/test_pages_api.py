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


def _rotations(content: bytes) -> list[int]:
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        return [p.rotation for p in doc]
    finally:
        doc.close()


def test_rotate_blank_pages_rotates_all(client):
    """No page list means 'all pages' (matches the UI's 'blank = all' hint)."""
    doc_id = _upload_pdf(client, ["A", "B", "C"])
    out = client.post(f"/documents/{doc_id}/pages/rotate", json={"pages": [], "degrees": 90})
    assert out.status_code == 200
    assert _rotations(out.content) == [90, 90, 90]


def test_delete_and_reorder_endpoints(client):
    doc_id = _upload_pdf(client, ["A", "B", "C"])

    # delete persists a new current version, so it mutates the stored document …
    out = client.post(f"/documents/{doc_id}/pages/delete", json={"pages": [1]})
    assert out.status_code == 200
    assert _page_texts(out.content) == ["A", "C"]

    # … and the next op operates on the now-2-page document (indices compound, not reset).
    out = client.post(f"/documents/{doc_id}/pages/reorder", json={"order": [1, 0]})
    assert out.status_code == 200
    assert _page_texts(out.content) == ["C", "A"]


def test_page_ops_persist_new_version(client):
    """In-place page ops update the stored document, not just the downloaded copy."""
    doc_id = _upload_pdf(client, ["A", "B", "C"])
    versions_before = len(client.get(f"/documents/{doc_id}/history").json()["versions"])

    out = client.post(f"/documents/{doc_id}/pages/delete", json={"pages": [1]})
    assert out.status_code == 200

    # The model now reflects two pages, and a new version was committed.
    model = client.get(f"/documents/{doc_id}/model").json()
    nodes = model["document"]["nodes"].values()
    assert sum(1 for n in nodes if n["type"] == "page") == 2
    versions_after = len(client.get(f"/documents/{doc_id}/history").json()["versions"])
    assert versions_after == versions_before + 1


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
