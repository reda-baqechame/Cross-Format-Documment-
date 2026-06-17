"""Track-changes / suggest mode over the API."""

from __future__ import annotations


def _upload(client):
    return client.post(
        "/documents", files={"file": ("s.txt", b"Original sentence here.", "text/plain")}
    ).json()["doc_id"]


def _first_run(client, doc_id):
    nodes = client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"]
    return next(nid for nid, n in nodes.items() if n["type"] == "run")


def _run_text(client, doc_id, node_id):
    return client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"][node_id]["text"]


def test_pending_suggestion_does_not_change_document(client):
    doc_id = _upload(client)
    run_id = _first_run(client, doc_id)
    before = _run_text(client, doc_id, run_id)

    made = client.post(
        f"/documents/{doc_id}/suggestions",
        json={
            "ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "Proposed."}}],
            "intent": "tighten wording",
            "author": "alice",
        },
    )
    assert made.status_code == 200
    assert made.json()["status"] == "pending"

    # Document is untouched while the suggestion is pending.
    assert _run_text(client, doc_id, run_id) == before
    pending = client.get(f"/documents/{doc_id}/suggestions?status=pending").json()
    assert len(pending["suggestions"]) == 1


def test_accept_applies_and_versions(client):
    doc_id = _upload(client)
    run_id = _first_run(client, doc_id)
    sid = client.post(
        f"/documents/{doc_id}/suggestions",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "Accepted!"}}]},
    ).json()["id"]

    out = client.post(f"/documents/{doc_id}/suggestions/{sid}/accept")
    assert out.status_code == 200
    body = out.json()
    assert body["status"] == "accepted"
    assert body["new_version_id"]

    assert _run_text(client, doc_id, run_id) == "Accepted!"
    # Accepted edit is a real version → undoable.
    assert client.post(f"/documents/{doc_id}/undo").status_code == 200


def test_reject_keeps_document_unchanged(client):
    doc_id = _upload(client)
    run_id = _first_run(client, doc_id)
    before = _run_text(client, doc_id, run_id)
    sid = client.post(
        f"/documents/{doc_id}/suggestions",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "nope"}}]},
    ).json()["id"]

    out = client.post(f"/documents/{doc_id}/suggestions/{sid}/reject").json()
    assert out["status"] == "rejected"
    assert _run_text(client, doc_id, run_id) == before


def test_cannot_decide_twice(client):
    doc_id = _upload(client)
    run_id = _first_run(client, doc_id)
    sid = client.post(
        f"/documents/{doc_id}/suggestions",
        json={"ops": [{"op": "set_text", "target_id": run_id, "payload": {"text": "x"}}]},
    ).json()["id"]
    assert client.post(f"/documents/{doc_id}/suggestions/{sid}/accept").status_code == 200
    assert client.post(f"/documents/{doc_id}/suggestions/{sid}/accept").status_code == 409
    assert client.post(f"/documents/{doc_id}/suggestions/{sid}/reject").status_code == 409


def test_validation_errors(client):
    doc_id = _upload(client)
    # unknown target node
    bad = client.post(
        f"/documents/{doc_id}/suggestions",
        json={"ops": [{"op": "set_text", "target_id": "nope", "payload": {"text": "x"}}]},
    )
    assert bad.status_code == 422
    assert client.get("/documents/missing/suggestions").status_code == 404
    assert (
        client.post(f"/documents/{doc_id}/suggestions/missing/accept").status_code == 404
    )
