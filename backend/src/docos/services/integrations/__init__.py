"""Cloud-storage integration seam (OAuth2 authorization-code).

A provider is **connected** only when its OAuth client id + secret are configured; until then
``connect`` returns 501 and the provider reads as not-connected. The OAuth handshake + token storage
are real; importing a file is a token-authenticated download of a provider content URL (the native
per-provider file *picker* would need each vendor's SDK — out of scope, documented honestly).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from docos.settings import Settings

_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    label: str
    authorize_url: str
    token_url: str
    scope: str


# OAuth endpoints per provider. Credentials come from settings (per-provider client id/secret).
_PROVIDERS: dict[str, ProviderSpec] = {
    "gdrive": ProviderSpec(
        "gdrive", "Google Drive",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/drive.readonly",
    ),
    "dropbox": ProviderSpec(
        "dropbox", "Dropbox",
        "https://www.dropbox.com/oauth2/authorize",
        "https://api.dropboxapi.com/oauth2/token",
        "files.content.read",
    ),
    "box": ProviderSpec(
        "box", "Box",
        "https://account.box.com/api/oauth2/authorize",
        "https://api.box.com/oauth2/token",
        "root_readonly",
    ),
    "onedrive": ProviderSpec(
        "onedrive", "OneDrive",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "Files.Read offline_access",
    ),
    "slack": ProviderSpec(
        "slack", "Slack",
        "https://slack.com/oauth/v2/authorize",
        "https://slack.com/api/oauth.v2.access",
        "files:read",
    ),
}


def provider_names() -> list[str]:
    return list(_PROVIDERS)


def get_spec(name: str) -> ProviderSpec | None:
    return _PROVIDERS.get(name)


def credentials(settings: Settings, name: str) -> tuple[str | None, str | None]:
    return (
        getattr(settings, f"{name}_client_id", None),
        getattr(settings, f"{name}_client_secret", None),
    )


def is_configured(settings: Settings, name: str) -> bool:
    cid, secret = credentials(settings, name)
    return bool(cid and secret and name in _PROVIDERS)


def redirect_uri(settings: Settings, name: str) -> str:
    base = (settings.oauth_redirect_base or "").rstrip("/")
    return f"{base}/api/integrations/{name}/callback"


def authorize_url(settings: Settings, name: str, *, state: str) -> str:
    spec = _PROVIDERS[name]
    cid, _ = credentials(settings, name)
    params = httpx.QueryParams(
        {
            "client_id": cid or "",
            "redirect_uri": redirect_uri(settings, name),
            "response_type": "code",
            "scope": spec.scope,
            "state": state,
            "access_type": "offline",
        }
    )
    return f"{spec.authorize_url}?{params}"


def exchange_code(settings: Settings, name: str, code: str) -> dict:
    """Exchange an authorization code for tokens. Raises on transport/HTTP error."""
    spec = _PROVIDERS[name]
    cid, secret = credentials(settings, name)
    resp = httpx.post(
        spec.token_url,
        data={
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redirect_uri(settings, name),
            "grant_type": "authorization_code",
        },
        timeout=_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def download(file_url: str, access_token: str) -> bytes:
    """Token-authenticated download of a provider content URL. Raises on error."""
    resp = httpx.get(
        file_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=_TIMEOUT_S,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content
