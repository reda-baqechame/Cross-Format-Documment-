"""Private Mode: delete all of the caller's documents in one call."""

from __future__ import annotations


def _upload(client, name: str) -> str:
    return client.post(
        "/documents", files={"file": (name, b"hello", "text/plain")}
    ).json()["doc_id"]


def test_purge_deletes_all_my_documents(client):
    _upload(client, "a.txt")
    _upload(client, "b.txt")
    assert len(client.get("/documents").json()["documents"]) == 2

    res = client.delete("/documents")
    assert res.status_code == 200
    assert res.json()["deleted"] == 2
    assert client.get("/documents").json()["documents"] == []


def test_purge_is_empty_when_nothing_to_delete(client):
    res = client.delete("/documents")
    assert res.status_code == 200
    assert res.json()["deleted"] == 0
