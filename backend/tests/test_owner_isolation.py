"""Per-session document isolation — the P0 IDOR fix.

Two anonymous sessions must never see, open, modify, export, or delete each other's
documents. Cross-owner access returns 404 (not 403), so the existence of an id never leaks.
"""

from __future__ import annotations

from docos.api.session import COOKIE_NAME


def _upload(client, data: bytes, name: str = "doc.pdf", mime: str = "application/pdf") -> str:
    res = client.post("/documents", files={"file": (name, data, mime)})
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def test_session_cookie_is_issued_httponly(client):
    res = client.get("/documents")
    assert res.status_code == 200
    # The cookie was set on first contact and is HttpOnly.
    set_cookie = res.headers.get("set-cookie", "")
    assert COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie.lower()
    assert client.cookies.get(COOKIE_NAME)


def test_two_sessions_cannot_see_each_others_documents(make_client, sample_pdf_bytes):
    alice = make_client()
    bob = make_client()

    doc_id = _upload(alice, sample_pdf_bytes)

    # Alice sees her own document.
    listed = alice.get("/documents").json()["documents"]
    assert [d["doc_id"] for d in listed] == [doc_id]
    assert alice.get(f"/documents/{doc_id}/model").status_code == 200

    # Bob's listing is empty and every direct access 404s (not 403 — no existence leak).
    assert bob.get("/documents").json()["documents"] == []
    assert bob.get(f"/documents/{doc_id}/model").status_code == 404
    assert bob.get(f"/documents/{doc_id}/history").status_code == 404
    assert bob.get(f"/documents/{doc_id}/extract").status_code == 404
    assert bob.get(f"/documents/{doc_id}/export?format=docx").status_code == 404
    assert bob.post(f"/documents/{doc_id}/patches", json={"instruction": "x"}).status_code == 404
    assert bob.delete(f"/documents/{doc_id}").status_code == 404

    # After all of Bob's attempts, Alice's document is intact.
    assert alice.get(f"/documents/{doc_id}/model").status_code == 200


def test_search_and_tags_are_session_scoped(make_client, sample_pdf_bytes):
    alice = make_client()
    bob = make_client()
    doc_id = _upload(alice, sample_pdf_bytes)
    alice.post(f"/documents/{doc_id}/tags", json={"tag": "Secret"})

    # Bob's full-text search and tag reads never reach Alice's content.
    assert bob.get("/search", params={"q": "Hello"}).json()["hits"] == []
    assert bob.get(f"/documents/{doc_id}/tags").status_code == 404
    # Alice can still find and read her own.
    assert any(
        h["doc_id"] == doc_id for h in alice.get("/search", params={"q": "Hello"}).json()["hits"]
    )


def test_owner_can_delete_then_its_gone(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}/model").status_code == 404
    assert client.get("/documents").json()["documents"] == []
