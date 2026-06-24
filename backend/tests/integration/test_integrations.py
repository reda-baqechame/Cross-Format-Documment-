"""Cloud integrations seam: honest not-connected default + a stubbed connect/import path."""

from __future__ import annotations

import docos.services.integrations as integrations
from docos.settings import get_settings


def test_integrations_list_is_not_connected_by_default(client):
    items = client.get("/integrations").json()["integrations"]
    names = {i["name"] for i in items}
    assert {"gdrive", "dropbox", "box", "onedrive", "slack"} <= names
    assert all(i["configured"] is False and i["connected"] is False for i in items)


def test_connect_501_when_unconfigured(client):
    res = client.get("/integrations/gdrive/connect")
    assert res.status_code == 501
    assert "not configured" in res.json()["detail"].lower()


def test_unknown_provider_404(client):
    assert client.get("/integrations/nope/connect").status_code == 404


def test_connect_returns_authorize_url_when_configured(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gdrive_client_id", "cid-123")
    monkeypatch.setattr(settings, "gdrive_client_secret", "secret-xyz")
    monkeypatch.setattr(settings, "oauth_redirect_base", "https://app.example.com")

    listed = client.get("/integrations").json()["integrations"]
    assert any(i["name"] == "gdrive" and i["configured"] for i in listed)

    res = client.get("/integrations/gdrive/connect")
    assert res.status_code == 200
    url = res.json()["authorize_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=cid-123" in url
    assert "redirect_uri=https" in url


def test_import_requires_connection(client):
    assert (
        client.post("/integrations/gdrive/import", json={"file_url": "https://x/y"}).status_code
        == 401
    )


def test_import_downloads_and_ingests_with_stub(client, monkeypatch):
    # Pretend the session has a stored token, and stub the provider download to return a txt file.
    from docos.db.models import IntegrationToken

    monkeypatch.setattr(integrations, "download", lambda url, token: b"Imported from the cloud.\n")

    # Seed a token by hitting the DB through a connected provider row.
    # Simplest: monkeypatch _token_for to return a fake token object.
    import docos.api.routes_integrations as routes

    monkeypatch.setattr(
        routes,
        "_token_for",
        lambda session, actor, name: IntegrationToken(
            id="itok_test", provider=name, access_token="tok"
        ),
    )
    res = client.post(
        "/integrations/dropbox/import",
        json={"file_url": "https://content/file", "filename": "note.txt"},
    )
    assert res.status_code == 200
    doc_id = res.json()["doc_id"]
    # The imported file went through the normal pipeline and is now a readable document.
    model = client.get(f"/documents/{doc_id}/model")
    assert model.status_code == 200
