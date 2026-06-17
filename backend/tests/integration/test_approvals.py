"""Approval / multi-party signing workflow over the API."""

from __future__ import annotations


def _upload(client):
    return client.post(
        "/documents", files={"file": ("d.txt", b"Contract body.", "text/plain")}
    ).json()["doc_id"]


def test_ordered_workflow_happy_path(client):
    doc_id = _upload(client)
    start = client.post(
        f"/documents/{doc_id}/approvals",
        json={"approvers": ["alice", "bob"], "ordered": True},
    )
    assert start.status_code == 200
    body = start.json()
    assert body["state"] == "in_progress"
    assert body["current_approvers"] == ["alice"]

    # bob can't jump the queue
    early = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "bob", "decision": "approve"},
    )
    assert early.status_code == 409

    a = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "alice", "decision": "approve"},
    ).json()
    assert a["current_approvers"] == ["bob"]
    assert a["state"] == "in_progress"

    b = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "bob", "decision": "approve"},
    ).json()
    assert b["state"] == "approved"
    assert b["current_approvers"] == []


def test_rejection_halts_workflow(client):
    doc_id = _upload(client)
    client.post(
        f"/documents/{doc_id}/approvals",
        json={"approvers": ["alice", "bob"], "ordered": True},
    )
    out = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "alice", "decision": "reject", "note": "needs work"},
    ).json()
    assert out["state"] == "rejected"
    assert out["current_approvers"] == []
    assert out["steps"][0]["note"] == "needs work"


def test_parallel_workflow_any_order(client):
    doc_id = _upload(client)
    client.post(
        f"/documents/{doc_id}/approvals",
        json={"approvers": ["x", "y"], "ordered": False},
    )
    status = client.get(f"/documents/{doc_id}/approvals").json()
    assert set(status["current_approvers"]) == {"x", "y"}
    client.post(
        f"/documents/{doc_id}/approvals/decision", json={"approver": "y", "decision": "approve"}
    )
    out = client.post(
        f"/documents/{doc_id}/approvals/decision", json={"approver": "x", "decision": "approve"}
    ).json()
    assert out["state"] == "approved"


def test_cannot_start_two_active_workflows(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["a"]})
    dup = client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["b"]})
    assert dup.status_code == 409


def test_can_restart_after_completion(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["a"]})
    client.post(
        f"/documents/{doc_id}/approvals/decision", json={"approver": "a", "decision": "approve"}
    )
    # finished → a fresh workflow may be started
    again = client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["b", "c"]})
    assert again.status_code == 200
    assert again.json()["state"] == "in_progress"


def test_validation_errors(client):
    doc_id = _upload(client)
    assert client.post(f"/documents/{doc_id}/approvals", json={"approvers": []}).status_code == 422
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["a"]})
    assert (
        client.post(
            f"/documents/{doc_id}/approvals/decision",
            json={"approver": "a", "decision": "maybe"},
        ).status_code
        == 422
    )
    assert client.get("/documents/nope/approvals").status_code == 404
