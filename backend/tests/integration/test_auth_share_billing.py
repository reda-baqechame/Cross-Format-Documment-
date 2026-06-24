"""Integration tests for auth, share portal, and billing seams."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from docos.db.models import Subscription


def _register(client, email: str, password: str = "password123") -> dict:
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def _upload(client, text: str = "Agency proposal for client.") -> str:
    res = client.post(
        "/documents",
        files={"file": ("prop.txt", text.encode(), "text/plain")},
    )
    assert res.status_code == 200, res.text
    return res.json()["doc_id"]


def test_register_login_and_claim(make_client):
    client_a = make_client()
    doc_id = _upload(client_a, "Session owned doc")

    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    reg = _register(client_a, email)
    assert reg["user"]["email"] == email
    assert reg["claimed"]["documents"] >= 1

    me = client_a.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    # Same session still sees the doc after claim (user_id path).
    model = client_a.get(f"/documents/{doc_id}/model")
    assert model.status_code == 200

    client_a.post("/auth/logout")
    assert client_a.get("/auth/me").json() is None


def test_share_requires_pro_plan(make_client, db):
    client = make_client()
    email = f"pro_{uuid.uuid4().hex[:8]}@example.com"
    reg = _register(client, email)
    user_id = reg["user"]["id"]
    doc_id = _upload(client)

    blocked = client.post(
        f"/documents/{doc_id}/shares",
        json={"permission": "view"},
    )
    assert blocked.status_code == 402

    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    assert sub is not None
    sub.plan = "pro"
    db.commit()

    ok = client.post(f"/documents/{doc_id}/shares", json={"permission": "view"})
    assert ok.status_code == 200, ok.text
    token = ok.json()["token"]

    portal = make_client()
    info = portal.get(f"/portal/{token}")
    assert info.status_code == 200
    model = portal.get(f"/portal/{token}/model")
    assert model.status_code == 200


def test_share_portal_with_pin_and_revoke(make_client, db):
    owner = make_client()
    other = make_client()
    email = f"pin_{uuid.uuid4().hex[:8]}@example.com"
    reg = _register(owner, email)
    user_id = reg["user"]["id"]
    doc_id = _upload(owner)
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    sub.plan = "pro"
    db.commit()

    created = owner.post(
        f"/documents/{doc_id}/shares",
        json={"permission": "view", "pin": "1234"},
    )
    assert created.status_code == 200, created.text
    token = created.json()["token"]

    portal = make_client()
    assert portal.get(f"/portal/{token}/model").status_code == 401
    model = portal.get(f"/portal/{token}/model", params={"pin": "1234"})
    assert model.status_code == 200

    share_id = created.json()["id"]
    assert other.delete(f"/documents/{doc_id}/shares/{share_id}").status_code == 404
    assert owner.delete(f"/documents/{doc_id}/shares/{share_id}").status_code == 200


def test_auth_rejects_weak_password(client):
    email = f"weak_{uuid.uuid4().hex[:8]}@example.com"
    assert client.post(
        "/auth/register",
        json={"email": email, "password": "short"},
    ).status_code == 422


def test_portal_sign_off(make_client, db):
    owner = make_client()
    email = f"sign_{uuid.uuid4().hex[:8]}@example.com"
    reg = _register(owner, email)
    user_id = reg["user"]["id"]
    doc_id = _upload(owner, "Contract for Alice Client.")

    owner.post(
        f"/documents/{doc_id}/approvals",
        json={"approvers": ["Alice Client"], "ordered": True},
    )

    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    sub.plan = "pro"
    db.commit()

    share = owner.post(
        f"/documents/{doc_id}/shares",
        json={"permission": "sign", "recipient_label": "Alice Client"},
    )
    assert share.status_code == 200, share.text
    token = share.json()["token"]

    portal = make_client()
    pending = portal.get(f"/portal/{token}/approvals")
    assert pending.status_code == 200
    assert pending.json()["state"] == "in_progress"

    approved = portal.post(f"/portal/{token}/approve")
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"


def test_billing_status_offline(make_client):
    client = make_client()
    res = client.get("/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert body["configured"] is False

    checkout = client.post("/billing/checkout", json={"plan": "pro"})
    assert checkout.status_code in (401, 501)
