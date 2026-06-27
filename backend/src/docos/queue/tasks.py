"""Background tasks.

Ingest defaults to synchronous (in-request), so by default no worker is required. When
``INGEST_MODE=async`` and ``CELERY_EAGER=false`` are set and a Celery worker is running against
``celery_app``, ``ingest_document`` does the parse/persist off the request path — the API enqueues
it and the client polls ``GET /jobs/{job_id}``. ``sweep_blob_tombstones`` retries failed blob
deletions. The API process imports ``ingest_document`` lazily (only on the real-worker branch), so
there is no import cycle and offline/sync use never touches Celery.
"""

from __future__ import annotations

from docos.queue.celery_app import celery_app


@celery_app.task(name="docos.ingest_document")
def ingest_document(
    blob_key: str, mime: str, detected_format: str, owner_session_id: str, job_id: str
) -> dict:
    """Re-parse a staged blob into the canonical model off the request path.

    Reads the staged bytes, runs the shared ``persist_document`` core (the exact parse → persist →
    version → audit path the synchronous route uses), and flips the queued ``JobRecord`` to its
    terminal state so progress/failures are observable from the ``jobs`` table. Runs in a worker
    process (no event loop), so ``asyncio.run`` is safe here.
    """
    import asyncio

    from docos.api.routes_documents import persist_document  # lazy: avoids an import cycle
    from docos.db.base import session_scope
    from docos.db.models import JobRecord
    from docos.deps import get_blob_store, get_registry

    blob_store = get_blob_store()
    registry = get_registry()
    try:
        data = asyncio.run(blob_store.get(blob_key))
        with session_scope() as session:
            record, version_id = asyncio.run(
                persist_document(
                    session,
                    data=data,
                    mime=mime,
                    detected_format=detected_format,
                    owner_session_id=owner_session_id,
                    blob_key=blob_key,
                    registry=registry,
                    blob_store=blob_store,
                    job_id=job_id,
                )
            )
        return {"status": "succeeded", "document_id": record.id, "version_id": version_id}
    except Exception as exc:  # noqa: BLE001 - record the failure on the job, never crash the worker
        with session_scope() as session:
            job = session.get(JobRecord, job_id)
            if job is not None and not job.finished:
                job.status = "failed"
                job.error = "ingest failed"
                job.finished = True
        return {"status": "failed", "error": str(exc)}


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
