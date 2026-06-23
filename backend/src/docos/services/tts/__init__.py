"""Text-to-speech (document → audio) provider seam.

There is no offline TTS engine bundled, so the default ``NoopTts`` is honest: it signals "not
configured" and the route returns 501. ``ExternalTts`` calls a TTS service over HTTPS when
``TTS_PROVIDER_URL`` is set and streams the audio back. Text is gathered redaction-aware so audio
never speaks content that was removed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import run_text

_TIMEOUT_S = 120.0


class TtsNotConfigured(RuntimeError):
    """Raised when synthesis is attempted without a configured provider."""


def document_text(doc: CanonicalDocument) -> str:
    """Redaction-aware plain text of the document, in reading order, for narration."""
    lines: list[str] = []
    if doc.meta.title:
        lines.append(doc.meta.title)
    for node in doc.walk():
        if node.type in ("heading", "paragraph", "list_item"):
            # Aggregate the block's run children (each run honors redaction).
            text = "".join(
                run_text(doc, child)
                for child in doc.children_of(node.id)
                if child.type == "run"
            ).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


class TtsProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(self, text: str, *, voice: str | None = None) -> tuple[bytes, str]:
        """Return ``(audio_bytes, content_type)``."""


class NoopTts(TtsProvider):
    name = "noop"

    def synthesize(self, text: str, *, voice: str | None = None) -> tuple[bytes, str]:
        raise TtsNotConfigured(
            "Text-to-speech is not configured — set TTS_PROVIDER_URL (+ TTS_PROVIDER_KEY) to "
            "enable document narration."
        )


class ExternalTts(TtsProvider):
    name = "external"

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def synthesize(self, text: str, *, voice: str | None = None) -> tuple[bytes, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(
            f"{self.base_url}/synthesize",
            headers=headers,
            json={"text": text, "voice": voice},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "audio/mpeg")
