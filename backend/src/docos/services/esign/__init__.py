"""E-signature provider seam.

The offline default (``SealProvider``) applies the existing HMAC **integrity seal** — tamper-evident
but explicitly *not* a legally-binding e-signature (no identity verification, no PKI/CA). A
regulated provider (DocuSign/Dropbox Sign/…) is wired through ``ExternalSignatureProvider`` over
plain HTTPS when ``SIGNATURE_PROVIDER_URL`` + key are set; otherwise the API stays honest.
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

_TIMEOUT_S = 30.0


class Signer(BaseModel):
    name: str
    email: str | None = None


class SignatureResult(BaseModel):
    provider: str  # "seal" | "external"
    status: str  # sealed | sent | completed | declined | error | pending
    external_id: str | None = None
    signing_url: str | None = None
    detail: str = ""
    legally_binding: bool = False


class SignatureProvider(ABC):
    name: str

    @abstractmethod
    def create_request(
        self, *, document: bytes, filename: str, signers: list[Signer], subject: str
    ) -> SignatureResult: ...

    @abstractmethod
    def status(self, external_id: str) -> SignatureResult: ...


class SealProvider(SignatureProvider):
    """Default: the integrity seal. Honest — tamper-evidence, not a legally-binding signature.

    The route performs the actual seal (``signing.sign`` + commit); this provider only reports the
    honest result shape so the API surface is uniform with the external provider.
    """

    name = "seal"

    def create_request(
        self, *, document: bytes, filename: str, signers: list[Signer], subject: str
    ) -> SignatureResult:
        return SignatureResult(
            provider="seal",
            status="sealed",
            detail=(
                "Integrity seal applied — any later change is detectable. This is tamper-evidence, "
                "not a legally-binding e-signature (no identity verification or PKI). Configure "
                "SIGNATURE_PROVIDER_URL + SIGNATURE_PROVIDER_KEY for regulated e-signature."
            ),
            legally_binding=False,
        )

    def status(self, external_id: str) -> SignatureResult:
        return SignatureResult(provider="seal", status="sealed", legally_binding=False)


class ExternalSignatureProvider(SignatureProvider):
    """Regulated e-signature over HTTPS, activated by SIGNATURE_PROVIDER_URL + key."""

    name = "external"

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def create_request(
        self, *, document: bytes, filename: str, signers: list[Signer], subject: str
    ) -> SignatureResult:
        try:
            resp = httpx.post(
                f"{self.base_url}/requests",
                headers=self._headers(),
                files={"document": (filename, document, "application/pdf")},
                data={
                    "subject": subject,
                    "signers": ",".join(s.email or s.name for s in signers),
                },
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never crash the route
            return SignatureResult(provider="external", status="error", detail=str(exc)[:300])
        return SignatureResult(
            provider="external",
            status=str(body.get("status", "sent")),
            external_id=str(body.get("id")) if body.get("id") is not None else None,
            signing_url=body.get("signing_url"),
            detail="Sent to the regulated e-signature provider.",
            legally_binding=True,
        )

    def status(self, external_id: str) -> SignatureResult:
        try:
            resp = httpx.get(
                f"{self.base_url}/requests/{external_id}",
                headers=self._headers(),
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            return SignatureResult(provider="external", status="error", detail=str(exc)[:300])
        return SignatureResult(
            provider="external",
            status=str(body.get("status", "pending")),
            external_id=external_id,
            signing_url=body.get("signing_url"),
            legally_binding=True,
        )


def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check on an inbound provider webhook."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
