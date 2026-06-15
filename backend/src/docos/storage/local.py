"""Filesystem-backed blob store — the zero-dependency default for offline mode."""

from __future__ import annotations

from pathlib import Path

from docos.storage.blob import BlobStore


class LocalBlobStore(BlobStore):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # keys may contain "/" to namespace; keep them within root
        safe = key.replace("..", "_")
        path = self.root / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def put(self, key: str, data: bytes) -> str:
        self._path(key).write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def url(self, key: str) -> str:
        return self._path(key).as_uri()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
