"""Bulk send — one packet to many recipients, each an independent sign-off."""

from __future__ import annotations


def _upload(client):
    return client.post(
        "/documents", files={"file": ("c.txt", b"Please sign this.", "text/plain")}
    ).json()["doc_id"]


def test_bulk_send_creates_independent_packets(client):
    doc_id = _upload(client)
    out = client.post(
        f"/documents/{doc_id}/bulk-send",
        json={"recipients": ["alice", "bob", "carol"], "message": "Please review"},
    )
    assert out.status_code == 200
    batch = out.json()
    assert len(batch["packets"]) == 3
    packet_ids = {p["packet_doc_id"] for p in batch["packets"]}
    assert doc_id not in packet_ids  # each packet is an independent copy
    assert len(packet_ids) == 3

    # Each packet is its own document with its own pending approval workflow.
    for p in batch["packets"]:
        assert p.get("portal_url", "").startswith("/portal/")
        wf = client.get(f"/documents/{p['packet_doc_id']}/approvals").json()
        assert wf["state"] == "in_progress"
        assert wf["current_approvers"] == [p["recipient"]]


def test_one_recipient_decision_does_not_affect_others(client):
    doc_id = _upload(client)
    batch = client.post(
        f"/documents/{doc_id}/bulk-send", json={"recipients": ["alice", "bob"]}
    ).json()
    alice = next(p for p in batch["packets"] if p["recipient"] == "alice")

    client.post(
        f"/documents/{alice['packet_doc_id']}/approvals/decision",
        json={"approver": "alice", "decision": "approve"},
    )

    listed = client.get(f"/documents/{doc_id}/bulk-send").json()
    assert len(listed["batches"]) == 1
    for packet in listed["batches"][0]["packets"]:
        assert packet.get("portal_url"), f"missing portal_url for {packet['recipient']}"
        assert packet["portal_url"].startswith("/portal/")
    states = {p["recipient"]: p["state"] for b in listed["batches"] for p in b["packets"]}
    assert states["alice"] == "approved"
    assert states["bob"] == "in_progress"  # unaffected by alice's decision


def test_validation_errors(client):
    doc_id = _upload(client)
    assert client.post(f"/documents/{doc_id}/bulk-send", json={"recipients": []}).status_code == 422
    assert (
        client.post(f"/documents/{doc_id}/bulk-send", json={"recipients": ["a", "a"]}).status_code
        == 422
    )
    assert client.post("/documents/nope/bulk-send", json={"recipients": ["a"]}).status_code == 404
    assert client.get("/documents/nope/bulk-send").status_code == 404
