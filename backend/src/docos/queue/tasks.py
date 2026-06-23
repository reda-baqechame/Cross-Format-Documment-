"""Background tasks — an **unwired future-scale seam**.

The app runs entirely synchronously in-request today (uploads, OCR, and patches all complete on
the request path), so nothing here is invoked in normal operation and no worker is required. This
module exists so heavy/batch work can be moved off the request path later by running a Celery
worker against ``celery_app``; the two tasks below are real, working extension points (large-file
ingest mirroring the sync route, and the tombstone sweeper). It is intentionally *not* imported by
the API process.
"""

from __future__ import annotations

from docos.queue.celery_app import celery_app


@celery_app.task(name="docos.ingest_document")
def ingest_document(blob_key: str, mime: str) -> dict:
    """Re-parse a staged blob into the canonical model asynchronously.

    Extension point: resolve the adapter, parse, and commit a version exactly as the
    synchronous route does, for large/batch uploads. Mirror the synchronous route's
    ``JobRecord`` bookkeeping (kind="ingest", status succeeded/failed) so progress and
    failures are observable from the ``jobs`` table.
    """
    return {"status": "queued", "blob_key": blob_key, "mime": mime}


@celery_app.task(name="docos.sweep_blob_tombstones")
def sweep_blob_tombstones() -> dict:
    """Retry blob deletions that failed during document delete (verified deletion).

    Schedule periodically so a storage hiccup never leaves user bytes behind.
    """
    import asyncio

    from docos.db.base import session_scope
    from docos.deps import get_blob_store
    from docos.services.provenance.deletion import sweep_tombstones

    with session_scope() as session:
        return asyncio.run(sweep_tombstones(session, get_blob_store()))
