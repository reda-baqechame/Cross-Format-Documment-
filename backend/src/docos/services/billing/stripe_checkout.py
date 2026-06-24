"""Stripe Checkout seam — activates when STRIPE_SECRET_KEY is set."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.db.models import Subscription
from docos.settings import get_settings


def _stripe_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=501, detail="stripe not configured")
    return {"Authorization": f"Bearer {settings.stripe_secret_key}"}


def create_checkout_session(
    session: Session,
    *,
    user_id: str,
    plan: str,
    email: str | None,
) -> str:
    settings = get_settings()
    price_id = settings.stripe_price_pro if plan == "pro" else settings.stripe_price_team
    if not price_id:
        raise HTTPException(status_code=501, detail=f"stripe price not configured for {plan}")

    sub = session.scalar(select(Subscription).where(Subscription.user_id == user_id))
    if sub is None:
        sub = Subscription(
            id=f"sub_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            plan="free",
            status="active",
        )
        session.add(sub)
        session.flush()

    return_url = settings.billing_return_url or "http://localhost:3100/pricing?success=1"
    data: dict[str, str] = {
        "mode": "subscription",
        "success_url": return_url,
        "cancel_url": return_url.replace("success=1", "canceled=1"),
        "client_reference_id": user_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "metadata[plan]": plan,
        "metadata[user_id]": user_id,
    }
    if email:
        data["customer_email"] = email
    if sub.stripe_customer_id:
        data["customer"] = sub.stripe_customer_id
        data.pop("customer_email", None)

    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={**_stripe_headers(), "Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )
    if res.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"stripe checkout failed: {res.text[:200]}")
    body = res.json()
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=502, detail="stripe did not return a checkout url")
    return url


def _verify_webhook(payload: bytes, signature: str) -> dict:
    settings = get_settings()
    secret = settings.stripe_webhook_secret
    if not secret:
        raise HTTPException(status_code=501, detail="stripe webhook not configured")
    parts = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in signature.split(",") if "=" in p}
    timestamp = parts.get("t")
    v1 = parts.get("v1")
    if not timestamp or not v1:
        raise HTTPException(status_code=400, detail="invalid stripe signature")
    signed = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        raise HTTPException(status_code=400, detail="invalid stripe signature")
    return json.loads(payload)


def handle_webhook(session: Session, *, payload: bytes, signature: str) -> None:
    event = _verify_webhook(payload, signature)
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        user_id = obj.get("client_reference_id") or obj.get("metadata", {}).get("user_id")
        plan = obj.get("metadata", {}).get("plan", "pro")
        if not user_id:
            return
        sub = session.scalar(select(Subscription).where(Subscription.user_id == user_id))
        if sub is None:
            sub = Subscription(
                id=f"sub_{uuid.uuid4().hex[:16]}",
                user_id=user_id,
                plan=plan,
                status="active",
            )
            session.add(sub)
        else:
            sub.plan = plan
            sub.status = "active"
        sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
        sub.stripe_subscription_id = obj.get("subscription") or sub.stripe_subscription_id

    elif etype == "customer.subscription.deleted":
        sub_id = obj.get("id")
        if sub_id:
            sub = session.scalar(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
            if sub:
                sub.plan = "free"
                sub.status = "canceled"
