"""Find & replace + redo over the route pipeline (deterministic, offline)."""

from __future__ import annotations


def _upload(client, body: bytes) -> str:
    return client.post(
        "/documents", files={"file": ("note.txt", body, "text/plain")}
    ).json()["doc_id"]


def _text(client, doc_id: str) -> str:
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    return "\n\n".join(
        n["text"] for n in model["nodes"].values() if n["type"] == "run"
    )


def test_replace_all_updates_document_and_reports_counts(client):
    doc_id = _upload(client, b"the cat sat\n\nthe cat ran")
    resp = client.post(f"/documents/{doc_id}/replace", json={"find": "cat", "replace": "dog"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["occurrences"] == 2
    assert body["nodes_changed"] == 2
    assert body["new_version_id"]
    assert "dog" in _text(client, doc_id) and "cat" not in _text(client, doc_id)


def test_replace_with_no_match_is_a_noop(client):
    doc_id = _upload(client, b"nothing to see here")
    resp = client.post(f"/documents/{doc_id}/replace", json={"find": "zzz", "replace": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert body["occurrences"] == 0
    assert body["new_version_id"] is None


def test_match_case_flag(client):
    doc_id = _upload(client, b"Cat and cat")
    resp = client.post(
        f"/documents/{doc_id}/replace",
        json={"find": "cat", "replace": "dog", "match_case": True},
    )
    assert resp.json()["occurrences"] == 1
    assert _text(client, doc_id) == "Cat and dog"


def test_replace_then_undo_then_redo_round_trip(client):
    doc_id = _upload(client, b"alpha beta alpha")
    client.post(f"/documents/{doc_id}/replace", json={"find": "alpha", "replace": "gamma"})
    assert _text(client, doc_id) == "gamma beta gamma"

    undo = client.post(f"/documents/{doc_id}/undo")
    assert undo.status_code == 200
    assert _text(client, doc_id) == "alpha beta alpha"

    redo = client.post(f"/documents/{doc_id}/redo")
    assert redo.status_code == 200
    assert _text(client, doc_id) == "gamma beta gamma"


def test_redo_with_nothing_to_redo_is_409(client):
    doc_id = _upload(client, b"just text")
    assert client.post(f"/documents/{doc_id}/redo").status_code == 409
