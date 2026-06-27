"""Async job status — the read side of the worker pipeline seam.

Ingest/OCR/patch work is recorded in the ``jobs`` table (``JobRecord``). Today most of it completes
synchronously in-request, but exposing job status here lets the frontend poll progress once heavy
parsing/OCR is moved off the request path onto a Celery worker. When a job is tied to a document the
caller must own that document, so one session can't read another's job records.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document
from docos.api.schemas import JobStatusResponse
from docos.api.session import Actor, get_actor
from docos.db.models import JobRecord
from docos.deps import db_session

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> JobStatusResponse:
    job = session.get(JobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    # When the job references a document, enforce ownership (404 on miss/cross-owner).
    if job.document_id is not None:
        get_owned_document(session, job.document_id, actor)
    return JobStatusResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        document_id=job.document_id,
        finished=job.finished,
        error=job.error,
    )
