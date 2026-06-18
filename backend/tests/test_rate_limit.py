"""Upload rate limiting — in-process token bucket, offline-friendly."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from docos.api import ratelimit
from docos.api.session import Actor


class _Req:
    def __init__(self, host: str = "1.2.3.4", headers: dict[str, str] | None = None) -> None:
        self.client = type("C", (), {"host": host})()
        self.headers = headers or {}


def _settings(enabled: bool, rate: int):
    return type("S", (), {"rate_limit_enabled": enabled, "rate_limit_uploads_per_min": rate})()


def test_bucket_blocks_after_burst(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings(True, 2))
    actor = Actor(session_id="sess-a")

    ratelimit.enforce_upload_rate(_Req(), actor)  # 1 — ok
    ratelimit.enforce_upload_rate(_Req(), actor)  # 2 — ok
    with pytest.raises(HTTPException) as exc:
        ratelimit.enforce_upload_rate(_Req(), actor)  # 3 — blocked
    assert exc.value.status_code == 429


def test_separate_sessions_have_separate_buckets(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings(True, 1))
    ratelimit.enforce_upload_rate(_Req(), Actor(session_id="a"))
    # A different session is unaffected by A exhausting its bucket.
    ratelimit.enforce_upload_rate(_Req(host="1.2.3.5"), Actor(session_id="b"))


def test_same_client_cannot_bypass_limit_by_rotating_session(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings(True, 1))
    req = _Req(headers={"x-forwarded-for": "203.0.113.9"})
    ratelimit.enforce_upload_rate(req, Actor(session_id="a"))
    with pytest.raises(HTTPException) as exc:
        ratelimit.enforce_upload_rate(req, Actor(session_id="b"))
    assert exc.value.status_code == 429


def test_disabled_flag_never_limits(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings(False, 1))
    actor = Actor(session_id="sess-c")
    for _ in range(10):
        ratelimit.enforce_upload_rate(_Req(), actor)  # no exception
