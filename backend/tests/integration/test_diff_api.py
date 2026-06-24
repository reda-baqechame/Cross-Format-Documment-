"""End-to-end cross-document compare endpoint."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_diff_two_documents(client):
    a = _upload(client, "Shared opening.\n\nOriginal clause.\n\nShared closing.")
    b = _upload(client, "Shared opening.\n\nRevised clause.\n\nShared closing.")
    res = client.get(f"/documents/{a}/diff", params={"against": b})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["changed"] == 1
    assert body["result"]["unchanged"] == 2


def test_diff_against_missing_document(client):
    a = _upload(client, "hello")
    assert client.get(f"/documents/{a}/diff", params={"against": "nope"}).status_code == 404
