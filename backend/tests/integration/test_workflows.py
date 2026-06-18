"""Guided business workflow preview and guarded execution."""

from __future__ import annotations


def _upload(client, text: str = "Master Services Agreement\nClient: Acme\nProvider: Globex"):
    res = client.post("/documents", files={"file": ("msa.txt", text.encode(), "text/plain")})
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def test_preview_contract_packet_is_non_mutating(client):
    doc_id = _upload(client)
    before = client.get(f"/documents/{doc_id}/history").json()["versions"]

    res = client.post(f"/documents/{doc_id}/workflows/preview", json={"preset": "contract_packet"})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["doc_id"] == doc_id
    assert body["preset"] == "contract_packet"
    assert [s["id"] for s in body["steps"]] == [
        "classify_extract",
        "prepare_fields",
        "approval_route",
        "export_validate",
    ]
    assert any(s["requires_approval"] for s in body["steps"])
    after = client.get(f"/documents/{doc_id}/history").json()["versions"]
    assert after == before


def test_execute_blocks_approval_route_without_explicit_approval(client):
    doc_id = _upload(client)
    res = client.post(
        f"/documents/{doc_id}/workflows/execute",
        json={"preset": "invoice_approval"},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["id"] for s in body["executed_steps"]] == [
        "classify_extract",
        "trust_checks",
        "export_validate",
    ]
    assert body["next_required_approval"]["id"] == "approval_route"
    assert client.get(f"/documents/{doc_id}/approvals").json()["state"] == "none"


def test_execute_starts_approved_approval_route(client):
    doc_id = _upload(client)
    res = client.post(
        f"/documents/{doc_id}/workflows/execute",
        json={
            "preset": "proposal_to_signature",
            "approved_step_ids": ["approval_route"],
            "approvers": ["legal@example.com", "finance@example.com"],
        },
    )

    assert res.status_code == 200, res.text
    assert any(s["id"] == "approval_route" for s in res.json()["executed_steps"])
    workflow = client.get(f"/documents/{doc_id}/approvals").json()
    assert workflow["state"] == "in_progress"
    assert workflow["current_approvers"] == ["legal@example.com"]


def test_bulk_send_requires_destructive_confirmation(client):
    doc_id = _upload(client)
    blocked = client.post(
        f"/documents/{doc_id}/workflows/execute",
        json={
            "preset": "bulk_send_template",
            "approved_step_ids": ["bulk_send"],
            "recipients": ["a@example.com", "b@example.com"],
        },
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["next_required_approval"]["id"] == "bulk_send"
    assert client.get(f"/documents/{doc_id}/bulk-send").json()["batches"] == []

    ok = client.post(
        f"/documents/{doc_id}/workflows/execute",
        json={
            "preset": "bulk_send_template",
            "approved_step_ids": ["bulk_send"],
            "confirm_destructive": True,
            "recipients": ["a@example.com", "b@example.com"],
        },
    )
    assert ok.status_code == 200, ok.text
    assert any(s["id"] == "bulk_send" for s in ok.json()["executed_steps"])
    batches = client.get(f"/documents/{doc_id}/bulk-send").json()["batches"]
    assert len(batches) == 1
    assert len(batches[0]["packets"]) == 2


def test_workflows_are_owner_scoped(make_client):
    alice = make_client()
    bob = make_client()
    doc_id = _upload(alice)
    res = bob.post(f"/documents/{doc_id}/workflows/preview", json={"preset": "contract_packet"})
    assert res.status_code == 404
