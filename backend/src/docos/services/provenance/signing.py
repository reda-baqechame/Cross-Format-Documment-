"""Deterministic, offline e-signature over the canonical content.

Signing computes an HMAC-SHA256 over the document's canonical hash (with the
signature state itself blanked, so the digest doesn't depend on prior signatures) and
records the signer + timestamp. Verification recomputes the digest and checks it
matches — so any edit after signing invalidates the signature, which is exactly the
tamper-evidence guarantee the trust panel promises. This is a self-contained scheme
for the offline build; a real deployment would swap in PKI / a signing authority.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, SignatureState
from docos.model.serialize import canonical_hash


def _content_digest(doc: CanonicalDocument, secret: str) -> str:
    probe = doc.model_copy(deep=True)
    # Blank the signature so the digest covers content only, not a prior signature.
    probe.signature = SignatureState(ready_for_signing=doc.signature.ready_for_signing)
    base = canonical_hash(probe)
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


def sign(doc: CanonicalDocument, *, signer: str, secret: str) -> CanonicalDocument:
    """Return a signed copy of the document."""
    signed = doc.model_copy(deep=True)
    digest = _content_digest(signed, secret)
    signed.signature = SignatureState(
        signed=True,
        signature_valid=True,
        ready_for_signing=False,
        signer=signer,
        signed_at=datetime.now(UTC),
        digest=digest,
    )
    return signed


def verify(doc: CanonicalDocument, *, secret: str) -> bool:
    """True if the document is signed and its content is unchanged since signing."""
    if not doc.signature.signed or not doc.signature.digest:
        return False
    return hmac.compare_digest(doc.signature.digest, _content_digest(doc, secret))
