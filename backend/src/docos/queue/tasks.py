"""Background tasks.

Ingestion of large files and OCR are slow and belong off the request path. The
synchronous upload route handles small files inline; this task proves the async
path and is the hook for batch/heavy work. OCR and patch tasks are stubs.
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


@celery_app.task(name="docos.run_ocr")
def run_ocr(doc_id: str) -> dict:
    raise NotImplementedError("run_ocr — invoke the OCR & structure service")


@celery_app.task(name="docos.apply_patch")
def apply_patch(doc_id: str, patch_id: str) -> dict:
    raise NotImplementedError("apply_patch — apply a stored reversible patch and commit a version")
