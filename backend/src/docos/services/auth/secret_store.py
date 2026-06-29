"""Small application-level envelope for reusable credentials stored in SQL."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "enc:v1:"


def _key(secret: str) -> bytes:
    return hashlib.sha256(b"docos-secret-store-v1\0" + secret.encode()).digest()


def seal(value: str | None, *, secret: str, context: str) -> str | None:
    if value is None:
        return None
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key(secret)).encrypt(nonce, value.encode(), context.encode())
    return _PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode()


def unseal(value: str | None, *, secret: str, context: str) -> str | None:
    if value is None or not value.startswith(_PREFIX):
        # Backward-compatible read for rows written before credential encryption.
        return value
    raw = base64.urlsafe_b64decode(value[len(_PREFIX) :].encode())
    return AESGCM(_key(secret)).decrypt(raw[:12], raw[12:], context.encode()).decode()
