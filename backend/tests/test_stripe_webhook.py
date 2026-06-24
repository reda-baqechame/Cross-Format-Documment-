"""Stripe webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException

from docos.services.billing import stripe_checkout


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    from docos.settings import get_settings

    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        stripe_checkout._verify_webhook(b"{}", "t=1,v1=deadbeef")
    assert exc.value.status_code == 400


def test_webhook_accepts_valid_signature(monkeypatch):
    secret = "whsec_test"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    from docos.settings import get_settings

    get_settings.cache_clear()
    payload = b'{"type":"ping"}'
    ts = str(int(time.time()))
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    event = stripe_checkout._verify_webhook(payload, f"t={ts},v1={sig}")
    assert event["type"] == "ping"


def test_webhook_rejects_stale_timestamp(monkeypatch):
    secret = "whsec_test"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    from docos.settings import get_settings

    get_settings.cache_clear()
    payload = b'{"type":"ping"}'
    ts = str(int(time.time()) - 600)
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HTTPException) as exc:
        stripe_checkout._verify_webhook(payload, f"t={ts},v1={sig}")
    assert exc.value.status_code == 400
    assert "stale" in exc.value.detail.lower()
