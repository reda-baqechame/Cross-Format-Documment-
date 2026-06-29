"""Regression proofs for the 2026-06 repository-wide security closure."""

from __future__ import annotations

import io
from urllib.parse import parse_qs, urlsplit

from docos.db.models import AuditEvent, Document, DocumentShare, IntegrationToken
from docos.services import integrations
from docos.settings import get_settings


def _upload(client, name: str = "d.txt", data: bytes = b"foo foo") -> str:
    return client.post(
        "/documents", files={"file": (name, data, "text/plain")}
    ).json()["doc_id"]


def test_cross_document_image_blob_refs_are_rejected(client, sample_image_bytes):
    source = _upload(client, "source.txt")
    target = _upload(client, "target.txt")
    blob_ref = client.post(
        f"/documents/{source}/assets",
        files={"file": ("asset.png", io.BytesIO(sample_image_bytes), "image/png")},
    ).json()["blob_ref"]
    root_id = client.get(f"/documents/{target}/model").json()["document"]["root_id"]
    op = {
        "op": "insert_image",
        "target_id": root_id,
        "payload": {"blob_ref": blob_ref, "mime": "image/png", "attrs": {"persisted": True}},
    }
    assert client.post(f"/documents/{target}/patches", json={"ops": [op]}).status_code == 422
    assert (
        client.post(
            f"/documents/{target}/suggestions",
            json={"ops": [op], "intent": "cross-object image"},
        ).status_code
        == 422
    )


def test_same_document_uploaded_image_ref_is_accepted(client, sample_image_bytes):
    doc_id = _upload(client)
    blob_ref = client.post(
        f"/documents/{doc_id}/assets",
        files={"file": ("asset.png", io.BytesIO(sample_image_bytes), "image/png")},
    ).json()["blob_ref"]
    root_id = client.get(f"/documents/{doc_id}/model").json()["document"]["root_id"]
    result = client.post(
        f"/documents/{doc_id}/patches",
        json={
            "ops": [
                {
                    "op": "insert_image",
                    "target_id": root_id,
                    "payload": {"blob_ref": blob_ref, "mime": "image/png"},
                }
            ]
        },
    )
    assert result.status_code == 200


def test_bulk_and_replace_input_limits_fail_before_expensive_work(client):
    doc_id = _upload(client)
    recipients = [f"person-{index}@example.com" for index in range(101)]
    assert (
        client.post(f"/documents/{doc_id}/bulk-send", json={"recipients": recipients}).status_code
        == 422
    )
    assert (
        client.post(
            f"/documents/{doc_id}/replace",
            json={"find": "foo", "replace": "x" * 10_001},
        ).status_code
        == 422
    )


def test_readiness_filename_cannot_inject_response_headers(client, db):
    doc_id = _upload(client)
    row = db.get(Document, doc_id)
    row.title = 'report"\r\nX-Evil: injected'
    db.commit()
    response = client.get(f"/documents/{doc_id}/readiness/report?format=json")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert response.headers.get("x-evil") is None


def test_share_lookup_is_hashed_and_bearer_is_encrypted(client, db, monkeypatch):
    import docos.api.routes_share as routes_share

    monkeypatch.setattr(routes_share, "require_portal_access", lambda session, actor: None)
    doc_id = _upload(client)
    created = client.post(
        f"/documents/{doc_id}/shares",
        json={"permission": "view", "recipient_label": "reader"},
    )
    assert created.status_code == 200
    raw = created.json()["token"]
    row = db.query(DocumentShare).filter_by(id=created.json()["id"]).one()
    assert row.token != raw
    assert row.token.startswith("hmac-sha256:")
    assert row.token_ciphertext and raw not in row.token_ciphertext
    assert client.get(f"/portal/{raw}").status_code == 200


def test_oauth_callback_encrypts_reusable_tokens(client, db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gdrive_client_id", "client-id")
    monkeypatch.setattr(settings, "gdrive_client_secret", "client-secret")
    monkeypatch.setattr(settings, "oauth_redirect_base", "https://app.example.com")
    monkeypatch.setattr(
        integrations,
        "exchange_code",
        lambda settings, name, code: {
            "access_token": "raw-access-token",
            "refresh_token": "raw-refresh-token",
        },
    )
    authorize_url = client.get("/integrations/gdrive/connect").json()["authorize_url"]
    state = parse_qs(urlsplit(authorize_url).query)["state"][0]
    callback = client.get(
        "/integrations/gdrive/callback",
        params={"code": "code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    row = db.query(IntegrationToken).filter_by(provider="gdrive").one()
    assert row.access_token.startswith("enc:v1:")
    assert row.refresh_token and row.refresh_token.startswith("enc:v1:")
    assert "raw-access-token" not in row.access_token
    assert "raw-refresh-token" not in row.refresh_token


def test_patch_audit_records_the_real_session_actor(client, db):
    doc_id = _upload(client)
    result = client.post(f"/documents/{doc_id}/replace", json={"find": "foo", "replace": "bar"})
    assert result.status_code == 200
    event = db.query(AuditEvent).filter_by(document_id=doc_id, action="text.replaced").one()
    assert event.actor and event.actor != "api"
