"""Comment threads: add / reply / resolve / delete, all versioned and undoable."""

from __future__ import annotations


def _upload(client, text=b"First paragraph.\n\nSecond paragraph."):
    return client.post("/documents", files={"file": ("d.txt", text, "text/plain")}).json()["doc_id"]


def _a_run_id(client, doc_id):
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    return next(n["id"] for n in model["nodes"].values() if n["type"] == "run")


def test_add_list_and_reply(client):
    doc_id = _upload(client)
    target = _a_run_id(client, doc_id)

    created = client.post(
        f"/documents/{doc_id}/comments",
        json={"text": "Please reword this", "target_id": target, "author": "alice"},
    )
    assert created.status_code == 200
    comment_id = created.json()["comment_id"]

    threads = client.get(f"/documents/{doc_id}/comments").json()["threads"]
    assert len(threads) == 1
    assert threads[0]["text"] == "Please reword this"
    assert threads[0]["target_id"] == target
    assert threads[0]["author"] == "alice"

    reply = client.post(
        f"/documents/{doc_id}/comments/{comment_id}/replies",
        json={"text": "Agreed", "author": "bob"},
    )
    assert reply.status_code == 200
    threads = client.get(f"/documents/{doc_id}/comments").json()["threads"]
    assert len(threads) == 1 and len(threads[0]["replies"]) == 1
    assert threads[0]["replies"][0]["text"] == "Agreed"


def test_document_level_comment_has_no_target(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/comments", json={"text": "Overall: good"})
    threads = client.get(f"/documents/{doc_id}/comments").json()["threads"]
    assert threads[0]["target_id"] is None


def test_resolve_and_reopen(client):
    doc_id = _upload(client)
    comment_id = client.post(f"/documents/{doc_id}/comments", json={"text": "fix"}).json()[
        "comment_id"
    ]

    client.post(f"/documents/{doc_id}/comments/{comment_id}/resolve", json={"resolved": True})
    threads = client.get(f"/documents/{doc_id}/comments").json()["threads"]
    assert threads[0]["resolved"] is True

    client.post(f"/documents/{doc_id}/comments/{comment_id}/resolve", json={"resolved": False})
    threads = client.get(f"/documents/{doc_id}/comments").json()["threads"]
    assert threads[0]["resolved"] is False


def test_delete_thread_removes_replies(client):
    doc_id = _upload(client)
    comment_id = client.post(f"/documents/{doc_id}/comments", json={"text": "top"}).json()[
        "comment_id"
    ]
    client.post(f"/documents/{doc_id}/comments/{comment_id}/replies", json={"text": "child"})

    client.delete(f"/documents/{doc_id}/comments/{comment_id}")
    assert client.get(f"/documents/{doc_id}/comments").json()["threads"] == []
    # the comment nodes are gone from the model entirely
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    assert not any(n["type"] == "comment" for n in model["nodes"].values())


def test_comment_is_undoable(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/comments", json={"text": "temporary"})
    assert len(client.get(f"/documents/{doc_id}/comments").json()["threads"]) == 1
    client.post(f"/documents/{doc_id}/undo")
    assert client.get(f"/documents/{doc_id}/comments").json()["threads"] == []


def test_errors(client):
    doc_id = _upload(client)
    assert client.post(f"/documents/{doc_id}/comments", json={"text": "  "}).status_code == 422
    assert (
        client.post(
            f"/documents/{doc_id}/comments", json={"text": "x", "target_id": "nope"}
        ).status_code
        == 422
    )
    missing = client.post(f"/documents/{doc_id}/comments/nope/replies", json={"text": "x"})
    assert missing.status_code == 404
