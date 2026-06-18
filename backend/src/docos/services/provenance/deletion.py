"""Verified deletion — retry the blob deletions that failed during document delete.

When a document is deleted but its blob couldn't be removed, the failure is recorded as a
:class:`BlobTombstone` (see ``routes_documents.delete_document``) instead of being swallowed.
This sweeper retries those deletions, marks the ones that succeed ``resolved``, and keeps the
last error on the ones that don't — so a "delete" promise can actually be verified, and
storage isn't left holding bytes the user asked to remove.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.db.models import AuditEvent, BlobTombstone
from docos.storage.blob import BlobStore

logger = logging.getLogger("docos.deletion")


async def sweep_tombstones(
    session: Session, blob_store: BlobStore, *, limit: int = 100
) -> dict[str, int]:
    """Retry unresolved blob-delete tombstones. Returns ``{"resolved", "failed"}`` counts."""
    rows = session.scalars(
        select(BlobTombstone)
        .where(BlobTombstone.resolved.is_(False))
        .order_by(BlobTombstone.created_at)
        .limit(limit)
    ).all()

    resolved = 0
    failed = 0
    for tombstone in rows:
        tombstone.attempts += 1
        try:
            await blob_store.delete(tombstone.blob_key)
        except Exception as exc:  # noqa: BLE001 - keep sweeping; record and retry next time
            tombstone.last_error = str(exc)
            failed += 1
            logger.warning("tombstone retry failed for %s: %s", tombstone.blob_key, exc)
            continue
        tombstone.resolved = True
        tombstone.last_error = None
        session.add(
            AuditEvent(
                document_id=None,
                action="blob.delete_resolved",
                actor="sweeper",
                detail={"blob_key": tombstone.blob_key, "attempts": tombstone.attempts},
            )
        )
        resolved += 1

    session.commit()
    return {"resolved": resolved, "failed": failed}
