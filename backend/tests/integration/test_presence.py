"""Live presence: heartbeat shows viewers, TTL evicts, and access is owner-gated."""

from __future__ import annotations

import pytest

from docos.deps import get_presence_hub


@pytest.fixture(autouse=True)
def _reset_hub():
    get_presence_hub().reset()
    yield
    get_presence_hub().reset()


def _upload(client) -> str:
    res = client.post("/documents", files={"file": ("d.txt", b"hi", "text/plain")})
    return res.json()["doc_id"]


def test_heartbeat_lists_active_viewers(client):
    doc_id = _upload(client)
    r1 = client.post(
        f"/documents/{doc_id}/presence", json={"viewer_id": "v1", "name": "Tab A"}
    ).json()
    assert [v["viewer_id"] for v in r1["viewers"]] == ["v1"]

    # A second open view (same session, different tab) appears as a distinct viewer.
    client.post(f"/documents/{doc_id}/presence", json={"viewer_id": "v2", "name": "Tab B"})
    listed = client.get(f"/documents/{doc_id}/presence").json()
    assert {v["viewer_id"] for v in listed["viewers"]} == {"v1", "v2"}
    assert listed["ttl_seconds"] > 0


def test_ttl_evicts_stale_viewers(client, monkeypatch):
    doc_id = _upload(client)
    client.post(f"/documents/{doc_id}/presence", json={"viewer_id": "v1"})
    # Force the hub's TTL to 0 so the next read prunes the stale heartbeat.
    monkeypatch.setattr(get_presence_hub(), "ttl", 0)
    import time

    time.sleep(0.01)
    assert client.get(f"/documents/{doc_id}/presence").json()["viewers"] == []


def test_presence_is_owner_gated(client, make_client):
    doc_id = _upload(client)
    other = make_client()
    assert other.post(f"/documents/{doc_id}/presence", json={"viewer_id": "v1"}).status_code == 404
    assert other.get(f"/documents/{doc_id}/presence").status_code == 404
