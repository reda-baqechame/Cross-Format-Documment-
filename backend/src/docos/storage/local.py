"""Filesystem-backed blob store — the zero-dependency default for offline mode."""

from __future__ import annotations

from pathlib import Path

from docos.storage.blob import BlobStore


class LocalBlobStore(BlobStore):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys may contain "/" for namespaces, but may never escape the root.
        relative = Path(key)
        if not key or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid blob key")
        root = self.root.resolve()
        path = (root / relative).resolve()
        if path != root and root not in path.parents:
            raise ValueError("blob key escapes storage root")
        return path

    async def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def url(self, key: str) -> str:
        return self._path(key).as_uri()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
