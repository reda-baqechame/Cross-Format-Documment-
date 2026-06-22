"""Send-Ready Check / Document X-Ray endpoint.

One read-only call answers "is this document safe and complete to send?" by composing the
existing detectors (sensitive-data scan, document health, unfilled fields) into a single
verdict + per-check breakdown. Read-only: it never commits a version.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import ReadinessResponse
from docos.api.session import Actor, get_actor
from docos.deps import db_session
from docos.services.provenance import readiness

router = APIRouter(prefix="/documents", tags=["readiness"])


@router.get("/{doc_id}/readiness", response_model=ReadinessResponse)
def document_readiness(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> ReadinessResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    report = readiness.build_report(doc)
    return ReadinessResponse(doc_id=doc_id, report=report)
