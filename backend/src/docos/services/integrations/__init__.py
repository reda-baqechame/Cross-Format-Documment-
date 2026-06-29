"""Cloud-storage integration seam (OAuth2 authorization-code).

A provider is **connected** only when its OAuth client id + secret are configured; until then
``connect`` returns 501 and the provider reads as not-connected. The OAuth handshake + token storage
are real; importing a file is a token-authenticated download of a provider content URL (the native
per-provider file *picker* would need each vendor's SDK — out of scope, documented honestly).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from docos.settings import Settings

_TIMEOUT_S = 30.0
_MAX_REDIRECTS = 3

_DOWNLOAD_HOST_SUFFIXES: dict[str, tuple[str, ...]] = {
    "gdrive": ("googleapis.com", "googleusercontent.com"),
    "dropbox": ("dropboxapi.com", "dropboxusercontent.com"),
    "box": ("box.com", "boxcloud.com"),
    "onedrive": ("microsoft.com", "sharepoint.com", "1drv.com"),
    "slack": ("slack.com", "slack-files.com"),
}


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
        "gdrive",
        "Google Drive",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/drive.readonly",
    ),
    "dropbox": ProviderSpec(
        "dropbox",
        "Dropbox",
        "https://www.dropbox.com/oauth2/authorize",
        "https://api.dropboxapi.com/oauth2/token",
        "files.content.read",
    ),
    "box": ProviderSpec(
        "box",
        "Box",
        "https://account.box.com/api/oauth2/authorize",
        "https://api.box.com/oauth2/token",
        "root_readonly",
    ),
    "onedrive": ProviderSpec(
        "onedrive",
        "OneDrive",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "Files.Read offline_access",
    ),
    "slack": ProviderSpec(
        "slack",
        "Slack",
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


def validate_download_url(name: str, file_url: str) -> str:
    """Return a provider-owned HTTPS URL or raise before credentials are attached."""

    parsed = urlsplit(file_url)
    host = (parsed.hostname or "").rstrip(".").lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError("provider download URL must be credential-free HTTPS")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("provider download URL cannot use an IP address")
    suffixes = _DOWNLOAD_HOST_SUFFIXES.get(name, ())
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes):
        raise ValueError(f"download URL is not owned by the {name} provider")
    return file_url


def download(name: str, file_url: str, access_token: str, max_bytes: int) -> bytes:
    """Download from a provider allowlist with redirect and response-size controls."""

    current = validate_download_url(name, file_url)
    with httpx.Client(timeout=_TIMEOUT_S, follow_redirects=False) as client:
        for redirect_count in range(_MAX_REDIRECTS + 1):
            with client.stream(
                "GET", current, headers={"Authorization": f"Bearer {access_token}"}
            ) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location or redirect_count >= _MAX_REDIRECTS:
                        raise ValueError("provider download exceeded the redirect limit")
                    current = validate_download_url(name, urljoin(current, location))
                    continue
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError("provider file exceeds the upload size limit")
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("provider file exceeds the upload size limit")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError("provider download failed")
