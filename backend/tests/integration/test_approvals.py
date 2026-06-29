"""Approval / multi-party signing workflow over the API."""

from __future__ import annotations

import pytest

import docos.api.routes_share as routes_share


@pytest.fixture(autouse=True)
def _enable_portal_for_approval_tests(monkeypatch):
    monkeypatch.setattr(routes_share, "require_portal_access", lambda session, actor: None)


def _upload(client):
    return client.post(
        "/documents", files={"file": ("d.txt", b"Contract body.", "text/plain")}
    ).json()["doc_id"]


def _portal(client, doc_id: str, approver: str) -> str:
    result = client.post(
        f"/documents/{doc_id}/shares",
        json={"permission": "sign", "recipient_label": approver},
    )
    assert result.status_code == 200
    return result.json()["portal_url"]


def _portal_decide(client, portal_url: str, decision: str = "approve", note: str | None = None):
    return client.post(f"{portal_url}/approve", json={"decision": decision, "note": note})


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
    alice = _portal(client, doc_id, "alice")
    bob = _portal(client, doc_id, "bob")

    # bob can't jump the queue
    early = _portal_decide(client, bob)
    assert early.status_code == 409

    a = _portal_decide(client, alice).json()
    assert a["current_approvers"] == ["bob"]
    assert a["state"] == "in_progress"

    b = _portal_decide(client, bob).json()
    assert b["state"] == "approved"
    assert b["current_approvers"] == []


def test_rejection_halts_workflow(client):
    doc_id = _upload(client)
    client.post(
        f"/documents/{doc_id}/approvals",
        json={"approvers": ["alice", "bob"], "ordered": True},
    )
    alice = _portal(client, doc_id, "alice")
    out = _portal_decide(client, alice, "reject", "needs work").json()
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
    x = _portal(client, doc_id, "x")
    y = _portal(client, doc_id, "y")
    _portal_decide(client, y)
    out = _portal_decide(client, x).json()
    assert out["state"] == "approved"


def test_cannot_start_two_active_workflows(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["a"]})
    dup = client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["b"]})
    assert dup.status_code == 409


def test_can_restart_after_completion(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["a"]})
    _portal_decide(client, _portal(client, doc_id, "a"))
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


def test_owner_cannot_impersonate_an_approver(client):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["alice"]})
    result = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "alice", "decision": "approve"},
    )
    assert result.status_code == 403


def test_matching_authenticated_user_can_decide(client):
    registered = client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "correct horse battery staple"},
    )
    assert registered.status_code == 200
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/approvals", json={"approvers": ["owner@example.com"]})
    result = client.post(
        f"/documents/{doc_id}/approvals/decision",
        json={"approver": "owner@example.com", "decision": "approve"},
    )
    assert result.status_code == 200
    assert result.json()["state"] == "approved"
