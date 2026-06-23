"""Enterprise hardening: cross-session isolation, input bounds, and rate limiting.

These guard the multi-tenant + abuse-resistance properties the new endpoints must hold.
"""

from __future__ import annotations

import pytest

from docos.api import ratelimit
from docos.settings import get_settings


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    ratelimit.reset()
    yield
    ratelimit.reset()


def _new_session_client(client):
    """A second, independent session (fresh cookies) on the same app."""
    c = client.__class__(client.app)
    c.cookies.clear()
    return c


def _upload(c, name: str = "d.txt") -> str:
    return c.post("/documents", files={"file": (name, b"secret data", "text/plain")}).json()[
        "doc_id"
    ]


# ── cross-session isolation (tenant boundary) ───────────────────────────────────────────

def test_other_session_cannot_clean_or_audit_or_autofill(client):
    doc_id = _upload(client)
    other = _new_session_client(client)
    assert other.post(f"/documents/{doc_id}/clean").status_code == 404
    assert other.get(f"/documents/{doc_id}/readiness").status_code == 404
    assert other.get(f"/documents/{doc_id}/redaction-audit").status_code == 404
    assert other.post(f"/documents/{doc_id}/autofill").status_code == 404


def test_purge_only_deletes_callers_documents(client):
    mine = _upload(client, "mine.txt")
    other = _new_session_client(client)
    theirs = _upload(other, "theirs.txt")

    assert client.delete("/documents").json()["deleted"] == 1  # only mine
    assert other.get(f"/documents/{theirs}/readiness").status_code == 200  # theirs survives
    assert mine  # (referenced)


def test_fill_profile_is_per_session(client):
    client.put("/fill-profile", json={"data": {"Name": "Mine"}})
    other = _new_session_client(client)
    assert other.get("/fill-profile").json()["data"] == {}  # no cross-session leak


# ── input bounds ────────────────────────────────────────────────────────────────────────

def test_fill_profile_rejects_oversized_value(client):
    res = client.put("/fill-profile", json={"data": {"x": "A" * 5000}})
    assert res.status_code == 422


def test_fill_profile_rejects_too_many_entries(client):
    big = {f"k{i}": "v" for i in range(500)}
    assert client.put("/fill-profile", json={"data": big}).status_code == 422


# ── rate limiting on expensive ops ──────────────────────────────────────────────────────

def test_op_rate_limit_eventually_429s(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_ops_per_min", 3)
    doc_id = _upload(client)
    statuses = [client.post(f"/documents/{doc_id}/autofill").status_code for _ in range(8)]
    assert 429 in statuses  # the bucket drains and throttles


def test_export_is_burst_limited_but_first_call_passes(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_ops_per_min", 3)
    doc_id = _upload(client)
    statuses = [
        client.get(f"/documents/{doc_id}/export", params={"format": "txt"}).status_code
        for _ in range(8)
    ]
    assert statuses[0] == 200  # a normal export works
    assert 429 in statuses  # rapid-fire bursts are throttled


def test_ai_ask_is_burst_limited(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_ops_per_min", 3)
    doc_id = _upload(client)
    statuses = [
        client.post(f"/documents/{doc_id}/ask", json={"question": "what is this?"}).status_code
        for _ in range(8)
    ]
    assert 429 in statuses
