"""Encryption-at-rest: blobs are ciphertext on disk and round-trip transparently."""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from docos.storage.encrypted import EncryptingBlobStore, derive_key
from docos.storage.local import LocalBlobStore


def test_derived_key_is_256_bit():
    assert len(derive_key("anything")) == 32


async def test_roundtrip_and_ciphertext_on_disk(tmp_path):
    inner = LocalBlobStore(str(tmp_path))
    store = EncryptingBlobStore(inner, derive_key("secret"))
    plaintext = b"the quick brown fox SSN 123-45-6789"

    await store.put("uploads/x", plaintext)
    # Caller sees plaintext back...
    assert await store.get("uploads/x") == plaintext
    # ...but the bytes actually persisted are encrypted and reveal nothing.
    raw = await inner.get("uploads/x")
    assert raw != plaintext
    assert b"SSN" not in raw
    assert raw.startswith(b"DXE1")


async def test_legacy_plaintext_passes_through(tmp_path):
    inner = LocalBlobStore(str(tmp_path))
    await inner.put("k", b"written before encryption")  # no magic header
    store = EncryptingBlobStore(inner, derive_key("secret"))
    assert await store.get("k") == b"written before encryption"


async def test_wrong_key_cannot_decrypt(tmp_path):
    inner = LocalBlobStore(str(tmp_path))
    await EncryptingBlobStore(inner, derive_key("k1")).put("k", b"data")
    with pytest.raises(InvalidTag):
        await EncryptingBlobStore(inner, derive_key("k2")).get("k")


def test_key_length_validated(tmp_path):
    with pytest.raises(ValueError):
        EncryptingBlobStore(LocalBlobStore(str(tmp_path)), b"too-short")


def test_get_blob_store_wraps_when_encryption_enabled(monkeypatch, tmp_path):
    import docos.deps as deps

    class _S:
        blob_backend = "local"
        local_blob_dir = str(tmp_path)
        blob_encryption = "aesgcm"
        blob_encryption_key = None
        signing_secret = "test-secret"
        s3_bucket = ""
        s3_endpoint_url = None
        s3_access_key = None
        s3_secret_key = None

    deps.get_blob_store.cache_clear()
    monkeypatch.setattr(deps, "get_settings", lambda: _S())
    try:
        assert isinstance(deps.get_blob_store(), EncryptingBlobStore)
    finally:
        deps.get_blob_store.cache_clear()
