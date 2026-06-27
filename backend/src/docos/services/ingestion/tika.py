"""Apache Tika fallback/validation seam (Tika is Apache-2.0).

Tika detects the type of, and extracts metadata + text from, 1,400+ file formats. It is wired as a
**fallback and validation** layer, never the primary parser: when a sidecar Tika server is set up
(``TIKA_SERVER_URL``), it can identify unknown uploads, surface embedded metadata, and provide a
text baseline to compare the native parser against. With no server configured every method returns
an empty/neutral result, so the platform's offline default is unaffected.
"""

from __future__ import annotations

import httpx

_TIMEOUT_S = 60.0


class TikaClient:
    """Thin HTTP client for a running Tika server (``/detect``, ``/meta``, ``/tika`` endpoints)."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def detect_mime(self, data: bytes) -> str | None:
        """Return Tika's detected media type for the bytes, or ``None`` on any failure."""
        try:
            resp = httpx.put(
                f"{self.base_url}/detect/stream",
                content=data,
                headers={"Accept": "text/plain"},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
        except Exception:  # noqa: BLE001 - detection is best-effort
            return None
        return resp.text.strip() or None

    def metadata(self, data: bytes) -> dict[str, str]:
        """Return embedded metadata Tika can read (empty dict on failure)."""
        try:
            resp = httpx.put(
                f"{self.base_url}/meta",
                content=data,
                headers={"Accept": "application/json"},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception:  # noqa: BLE001 - metadata extraction is best-effort
            return {}
        return {str(k): str(v) for k, v in body.items()}

    def extract_text(self, data: bytes) -> str:
        """Return Tika's plain-text extraction (empty string on failure).

        Used only to validate/compare against the native parser — never as the canonical content.
        """
        try:
            resp = httpx.put(
                f"{self.base_url}/tika",
                content=data,
                headers={"Accept": "text/plain"},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
        except Exception:  # noqa: BLE001 - extraction is best-effort
            return ""
        return resp.text
