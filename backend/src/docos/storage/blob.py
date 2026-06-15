"""``BlobStore`` interface — raw bytes live here, never inline in the model."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BlobStore(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key`` and return the key."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``."""

    @abstractmethod
    async def url(self, key: str) -> str:
        """Return an addressable (possibly short-lived signed) URL for ``key``."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove ``key`` if present."""
