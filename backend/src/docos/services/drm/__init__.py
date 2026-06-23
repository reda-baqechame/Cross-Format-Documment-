"""DRM / rights-management provider seam.

Real DRM (usage policies, license servers, revocation) needs a rights-management service, so there
is no offline default — ``DrmProvider`` activates only when ``DRM_PROVIDER_URL`` is configured. The
honest local protection meanwhile is AES-256 PDF passwording (``pageops.encrypt_pdf``); the API says
so rather than implying DRM it doesn't have.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

_TIMEOUT_S = 60.0


class DrmProvider(ABC):
    name: str

    @abstractmethod
    def apply(self, data: bytes, mime: str, *, policy: str | None = None) -> tuple[bytes, str]:
        """Return ``(protected_bytes, content_type)``."""


class ExternalDrm(DrmProvider):
    name = "external"

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def apply(self, data: bytes, mime: str, *, policy: str | None = None) -> tuple[bytes, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(
            f"{self.base_url}/protect",
            headers=headers,
            files={"document": ("document", data, mime)},
            data={"policy": policy or "default"},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", mime)
