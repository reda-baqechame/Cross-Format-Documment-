"""Document classification + translation endpoints."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_classify_invoice(client):
    doc_id = _upload(
        client, "INVOICE\n\nBill To: Acme\n\nSubtotal: $10\n\nTotal Due: $12 by due date"
    )
    body = client.get(f"/documents/{doc_id}/classify").json()["classification"]
    assert body["label"] == "invoice"
    assert body["confidence"] > 0
    assert body["signals"]


def test_classify_other_when_no_signals(client):
    doc_id = _upload(client, "just some neutral words here")
    assert client.get(f"/documents/{doc_id}/classify").json()["classification"]["label"] == "other"


def test_translate_requires_llm_provider_offline(client):
    doc_id = _upload(client, "hello world")
    res = client.post(f"/documents/{doc_id}/translate", json={"target_language": "French"})
    assert res.status_code == 501  # noop provider in tests
