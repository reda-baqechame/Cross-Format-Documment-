"""Deletion correctness — failed blob deletes are recorded, never silently swallowed."""

from __future__ import annotations

import docos.deps as deps
from docos.db.models import AuditEvent, BlobTombstone
from docos.storage.blob import BlobStore


class _FlakyBlobStore(BlobStore):
    """Accepts writes/reads but fails every delete — simulates a storage outage."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> str:
        self._data[key] = data
        return key

    async def get(self, key: str) -> bytes:
        return self._data[key]

    async def url(self, key: str) -> str:
        return key

    async def delete(self, key: str) -> None:
        raise OSError("storage unavailable")


def test_blob_delete_failure_records_tombstone(client, db, sample_pdf_bytes, monkeypatch):
    store = _FlakyBlobStore()
    monkeypatch.setattr(deps, "get_blob_store", lambda: store)

    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", sample_pdf_bytes, "application/pdf")}
    ).json()["doc_id"]

    # Delete still succeeds from the caller's perspective (DB row is gone)...
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}/model").status_code == 404

    # ...but the failed blob delete is durably recorded, not swallowed.
    tombstones = db.query(BlobTombstone).all()
    assert len(tombstones) == 1
    assert tombstones[0].reason == "delete_failed"
    assert tombstones[0].resolved is False

    events = {e.action for e in db.query(AuditEvent).all()}
    assert "document.blob_delete_failed" in events
