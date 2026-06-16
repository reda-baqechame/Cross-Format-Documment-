"""Tags + cross-corpus full-text search."""

from __future__ import annotations


def _upload(client, text: str, name: str = "d.txt") -> str:
    return client.post("/documents", files={"file": (name, text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_tag_lifecycle_and_list_filter(client):
    doc_id = _upload(client, "anything")
    assert client.post(f"/documents/{doc_id}/tags", json={"tag": "Legal"}).json()["tags"] == [
        "Legal"
    ]
    # idempotent add
    client.post(f"/documents/{doc_id}/tags", json={"tag": "Legal"})
    body = client.post(f"/documents/{doc_id}/tags", json={"tag": "Q3"}).json()
    assert body["tags"] == ["Legal", "Q3"]

    listed = client.get("/documents", params={"tag": "Legal"}).json()["documents"]
    assert any(d["doc_id"] == doc_id and "Legal" in d["tags"] for d in listed)
    assert client.get("/documents", params={"tag": "Nonexistent"}).json()["documents"] == []

    after = client.request("DELETE", f"/documents/{doc_id}/tags/Legal").json()
    assert after["tags"] == ["Q3"]


def test_search_across_documents(client):
    _upload(client, "The quarterly revenue report mentions synergy.")
    _upload(client, "An unrelated note about gardening.")
    hits = client.get("/search", params={"q": "synergy"}).json()["hits"]
    assert len(hits) == 1
    assert "synergy" in hits[0]["snippet"].lower()


def test_search_skips_redacted(client):
    doc_id = _upload(client, "keep me\n\ntopsecret token")
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    node = next(n["id"] for n in model["nodes"].values() if n.get("text") == "topsecret token")
    client.post(f"/documents/{doc_id}/patches", json={"ops": [{"op": "redact", "target_id": node}]})
    assert client.get("/search", params={"q": "topsecret"}).json()["hits"] == []
