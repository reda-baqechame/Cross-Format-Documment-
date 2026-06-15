"""Semantic patch endpoint.

Turns a natural-language instruction into a reversible patch, applies it, and (when
it changes anything) commits a new version. With the offline noop client the patch is
a no-op, but the whole interpret→apply→commit path is exercised end to end.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import PatchRequest, PatchResponse
from docos.db.models import Document
from docos.deps import db_session, get_orchestrator, get_provenance

router = APIRouter(prefix="/documents", tags=["semantic"])


@router.post("/{doc_id}/patches", response_model=PatchResponse)
async def create_patch(
    doc_id: str, body: PatchRequest, session: Session = Depends(db_session)
) -> PatchResponse:
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    patch = await orchestrator.interpret(doc, body.instruction)
    applied = bool(patch.patches)
    new_version_id: str | None = None

    if applied:
        updated = orchestrator.apply(doc, patch)
        new_version_id = provenance.commit_version(updated, patch=patch)
        record = session.get(Document, doc_id)
        if record is not None:
            record.current_version_id = new_version_id

    provenance.record_event(
        doc_id,
        "patch.created",
        actor="api",
        detail={"patch_id": patch.id, "applied": applied, "intent": patch.intent},
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=applied,
        new_version_id=new_version_id,
        intent=patch.intent,
    )
