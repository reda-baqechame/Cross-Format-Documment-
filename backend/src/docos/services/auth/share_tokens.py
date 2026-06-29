"""Non-recoverable lookup plus application-encrypted recovery for portal tokens."""

from __future__ import annotations

import hashlib
import hmac

from docos.services.auth.secret_store import seal, unseal

_DIGEST_PREFIX = "hmac-sha256:"


def token_digest(token: str, *, secret: str) -> str:
    digest = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    return _DIGEST_PREFIX + digest


def protect_share_token(token: str, *, secret: str, share_id: str) -> tuple[str, str]:
    ciphertext = seal(token, secret=secret, context=f"share:{share_id}")
    assert ciphertext is not None
    return token_digest(token, secret=secret), ciphertext


def recover_share_token(
    stored_lookup: str,
    stored_ciphertext: str | None,
    *,
    secret: str,
    share_id: str,
) -> str:
    if stored_ciphertext is None:
        return stored_lookup
    token = unseal(stored_ciphertext, secret=secret, context=f"share:{share_id}")
    if token is None:
        raise ValueError("share token ciphertext is empty")
    return token
