"""Document listing, deletion, and version-DAG undo over the route pipeline."""

from __future__ import annotations


def _upload(client, body: bytes = b"first text") -> str:
    return client.post(
        "/documents", files={"file": ("note.txt", body, "text/plain")}
    ).json()["doc_id"]


def _first_run_id(client, doc_id: str) -> str:
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    return next(n["id"] for n in model["nodes"].values() if n["type"] == "run")


def test_list_documents(client):
    a = _upload(client, b"doc a")
    b = _upload(client, b"doc b")
    listing = client.get("/documents")
    assert listing.status_code == 200
    ids = {d["doc_id"] for d in listing.json()["documents"]}
    assert {a, b} <= ids


def test_undo_reverts_to_previous_version(client):
    doc_id = _upload(client, b"before edit")
    run_id = _first_run_id(client, doc_id)
    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "after edit"}}]},
    )

    def run_text() -> str:
        model = client.get(f"/documents/{doc_id}/model").json()["document"]
        return model["nodes"][run_id]["text"]

    assert run_text() == "after edit"

    undo = client.post(f"/documents/{doc_id}/undo")
    assert undo.status_code == 200
    assert run_text() == "before edit"


def test_natural_language_edit_without_ai_returns_501(client):
    """Offline (noop provider), a natural-language instruction is a clear 501, not a no-op."""
    doc_id = _upload(client, b"before edit")
    resp = client.post(f"/documents/{doc_id}/patches", json={"instruction": "make it formal"})
    assert resp.status_code == 501
    assert "AI provider" in resp.json()["detail"]


def test_explicit_ops_still_apply_offline(client):
    """Deterministic ops do not require AI and must keep working offline."""
    doc_id = _upload(client, b"before edit")
    run_id = _first_run_id(client, doc_id)
    resp = client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "after"}}]},
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] is True


def test_undo_with_no_history_is_409(client):
    doc_id = _upload(client)
    resp = client.post(f"/documents/{doc_id}/undo")
    assert resp.status_code == 409


def test_delete_document(client):
    doc_id = _upload(client)
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}/model").status_code == 404
    ids = {d["doc_id"] for d in client.get("/documents").json()["documents"]}
    assert doc_id not in ids
