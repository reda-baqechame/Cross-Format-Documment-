"""Verified deletion: the tombstone sweeper retries failed blob deletes."""

from __future__ import annotations

from docos.db.models import AuditEvent, BlobTombstone
from docos.services.provenance.deletion import sweep_tombstones
from docos.storage.blob import BlobStore


class _Store(BlobStore):
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.deleted: list[str] = []

    async def put(self, key: str, data: bytes) -> str:
        return key

    async def get(self, key: str) -> bytes:
        return b""

    async def url(self, key: str) -> str:
        return key

    async def delete(self, key: str) -> None:
        if self.fail:
            raise OSError("storage still down")
        self.deleted.append(key)


async def test_sweep_resolves_when_storage_recovers(db):
    db.add(BlobTombstone(blob_key="b1", reason="delete_failed"))
    db.commit()

    result = await sweep_tombstones(db, _Store(fail=False))

    assert result == {"resolved": 1, "failed": 0}
    t = db.query(BlobTombstone).one()
    assert t.resolved is True
    assert t.attempts == 1
    assert t.last_error is None
    actions = {e.action for e in db.query(AuditEvent).all()}
    assert "blob.delete_resolved" in actions


async def test_sweep_records_failure_and_leaves_unresolved(db):
    db.add(BlobTombstone(blob_key="b1", reason="delete_failed"))
    db.commit()

    result = await sweep_tombstones(db, _Store(fail=True))

    assert result == {"resolved": 0, "failed": 1}
    t = db.query(BlobTombstone).one()
    assert t.resolved is False
    assert t.attempts == 1
    assert "down" in (t.last_error or "")
