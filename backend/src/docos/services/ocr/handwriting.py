"""Handwriting OCR provider seam.

Standard OCR (Tesseract) recognizes printed text well but not handwriting. This seam calls a
specialized handwriting model over HTTPS when ``HANDWRITING_PROVIDER_URL`` is configured; without it
there is no handwriting recognition (the app falls back to standard OCR and says so honestly).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

_TIMEOUT_S = 60.0


class HandwritingProvider(ABC):
    name: str

    @abstractmethod
    def recognize(self, image: bytes, mime: str = "image/png") -> str:
        """Return recognized handwriting text (empty string if none/failure)."""


class ExternalHandwriting(HandwritingProvider):
    name = "external"

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def recognize(self, image: bytes, mime: str = "image/png") -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = httpx.post(
                f"{self.base_url}/recognize",
                headers=headers,
                files={"image": ("image", image, mime)},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
            return str(resp.json().get("text", ""))
        except Exception:  # noqa: BLE001 - best-effort enhancement; never crash the caller
            return ""
