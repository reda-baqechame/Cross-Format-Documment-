"""Document-health endpoint backing the frontend health panel."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import DocumentHealthResponse
from docos.deps import db_session, get_provenance

router = APIRouter(prefix="/documents", tags=["health"])


@router.get("/{doc_id}/health", response_model=DocumentHealthResponse)
def document_health(doc_id: str, session: Session = Depends(db_session)) -> DocumentHealthResponse:
    _record, doc = _load_latest(session, doc_id)
    health = get_provenance(session).compute_health(doc)
    return DocumentHealthResponse(doc_id=doc_id, health=health)
