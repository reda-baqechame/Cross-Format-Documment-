"""Unit-level negative controls for storage, URL, and credential boundaries."""

from __future__ import annotations

import asyncio

import pytest
from cryptography.exceptions import InvalidTag

from docos.services.auth.secret_store import seal, unseal
from docos.services.integrations import validate_download_url
from docos.storage.local import LocalBlobStore


@pytest.mark.parametrize(
    "url",
    [
        "http://www.googleapis.com/file",
        "https://127.0.0.1/file",
        "https://metadata.google.internal/file",
        "https://evil.example/file",
        "https://token@www.googleapis.com/file",
    ],
)
def test_provider_download_url_rejects_untrusted_destinations(url):
    with pytest.raises(ValueError):
        validate_download_url("gdrive", url)


def test_provider_download_url_accepts_provider_https():
    url = "https://www.googleapis.com/drive/v3/files/id?alt=media"
    assert validate_download_url("gdrive", url) == url


def test_local_blob_store_rejects_absolute_and_parent_paths(tmp_path):
    store = LocalBlobStore(str(tmp_path / "blobs"))
    for key in ("../secret.png", "/absolute/secret.png", "safe/../../secret.png"):
        with pytest.raises(ValueError):
            asyncio.run(store.get(key))


def test_secret_store_round_trip_and_context_binding():
    protected = seal("credential", secret="test-secret", context="integration:one")
    assert protected and protected.startswith("enc:v1:") and "credential" not in protected
    assert (
        unseal(protected, secret="test-secret", context="integration:one") == "credential"
    )
    with pytest.raises(InvalidTag):
        unseal(protected, secret="test-secret", context="integration:two")
