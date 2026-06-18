"""Transparent application-level encryption-at-rest for blobs (AES-256-GCM).

Wraps any :class:`BlobStore`: bytes are encrypted on ``put`` and decrypted on ``get``, so
callers (ingestion, export, preview) never see ciphertext and need no changes. Each object
carries its own random nonce, and a small magic header lets ``get`` transparently pass through
blobs written *before* encryption was enabled (so turning it on doesn't strand existing data).

This is opt-in (``BLOB_ENCRYPTION=aesgcm``); the offline default stores plaintext, exactly like
the malware scanner defaults to noop. Defense in depth — it does not replace disk/bucket
encryption, it adds an application-controlled layer with its own key.
"""

from __future__ import annotations

import hashlib
import os

from docos.storage.blob import BlobStore

_MAGIC = b"DXE1"  # DocOS encrypted, v1
_NONCE_LEN = 12


def derive_key(secret: str) -> bytes:
    """A 32-byte AES-256 key from a configured secret (SHA-256)."""
    return hashlib.sha256(secret.encode()).digest()


class EncryptingBlobStore(BlobStore):
    def __init__(self, inner: BlobStore, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("blob encryption key must be 32 bytes")
        self._inner = inner
        self._key = key

    def _encrypt(self, data: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(_NONCE_LEN)
        ciphertext = AESGCM(self._key).encrypt(nonce, data, None)
        return _MAGIC + nonce + ciphertext

    def _decrypt(self, blob: bytes) -> bytes:
        if not blob.startswith(_MAGIC):
            return blob  # legacy plaintext written before encryption was enabled
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = blob[len(_MAGIC) : len(_MAGIC) + _NONCE_LEN]
        ciphertext = blob[len(_MAGIC) + _NONCE_LEN :]
        return AESGCM(self._key).decrypt(nonce, ciphertext, None)

    async def put(self, key: str, data: bytes) -> str:
        return await self._inner.put(key, self._encrypt(data))

    async def get(self, key: str) -> bytes:
        return self._decrypt(await self._inner.get(key))

    async def url(self, key: str) -> str:
        # The stored object is ciphertext; a direct URL isn't servable. Reads go through
        # get() (which decrypts), so this just delegates for parity.
        return await self._inner.url(key)

    async def delete(self, key: str) -> None:
        await self._inner.delete(key)
