"""Sign → verify → tamper over the route pipeline."""

from __future__ import annotations


def _upload(client, body: bytes = b"agreement text") -> str:
    return client.post(
        "/documents", files={"file": ("c.txt", body, "text/plain")}
    ).json()["doc_id"]


def _first_run_id(client, doc_id: str) -> str:
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    return next(n["id"] for n in model["nodes"].values() if n["type"] == "run")


def test_sign_and_verify(client):
    doc_id = _upload(client)

    status = client.get(f"/documents/{doc_id}/signature").json()
    assert status["signed"] is False

    signed = client.post(f"/documents/{doc_id}/sign", json={"signer": "Alice Adams"})
    assert signed.status_code == 200, signed.text
    assert signed.json()["signed"] is True and signed.json()["valid"] is True

    again = client.get(f"/documents/{doc_id}/signature").json()
    assert again["valid"] is True and again["signer"] == "Alice Adams"
    assert client.get(f"/documents/{doc_id}/health").json()["health"]["signed"] is True


def test_edit_after_signing_breaks_signature(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/sign", json={"signer": "Alice"})

    run_id = _first_run_id(client, doc_id)
    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "altered"}}]},
    )

    status = client.get(f"/documents/{doc_id}/signature").json()
    assert status["signed"] is True
    assert status["valid"] is False  # tamper detected


def test_sign_requires_signer(client):
    doc_id = _upload(client)
    assert client.post(f"/documents/{doc_id}/sign", json={"signer": ""}).status_code == 422
