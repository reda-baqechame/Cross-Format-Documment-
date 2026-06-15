"""Patch endpoint — the single "mutate the document" entry point.

Accepts either a natural-language ``instruction`` (routed through the LLM, a no-op
with the offline client) or an explicit list of deterministic ``ops`` (set_text,
update_node, retag, redact, …). In both cases the resulting reversible patch flows
through the same apply → commit_version → audit path, so every edit is versioned and
undoable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import PatchRequest, PatchResponse
from docos.db.models import Document
from docos.deps import db_session, get_orchestrator, get_provenance
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch

router = APIRouter(prefix="/documents", tags=["semantic"])

# Ops that act on an existing node and therefore require a valid ``target_id``.
_TARGETED_OPS = frozenset(
    {"set_text", "update_node", "retag", "redact", "unredact", "remove_node", "move_node"}
)


@router.post("/{doc_id}/patches", response_model=PatchResponse)
async def create_patch(
    doc_id: str, body: PatchRequest, session: Session = Depends(db_session)
) -> PatchResponse:
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    if body.ops:
        for op in body.ops:
            if op.op in _TARGETED_OPS and (op.target_id is None or op.target_id not in doc.nodes):
                raise HTTPException(status_code=422, detail=f"unknown target_id for op '{op.op}'")
        patch = ReversiblePatch(
            id=new_patch_id(),
            patches=[Patch(op=o.op, target_id=o.target_id, payload=o.payload) for o in body.ops],
            inverse=[],
            intent=body.instruction,
            created_at=datetime.now(timezone.utc),
        )
    else:
        patch = await orchestrator.interpret(doc, body.instruction or "")

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
        detail={
            "patch_id": patch.id,
            "applied": applied,
            "intent": patch.intent,
            "explicit": bool(body.ops),
        },
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=applied,
        new_version_id=new_version_id,
        intent=patch.intent,
    )


@router.post("/{doc_id}/sanitize-metadata", response_model=PatchResponse)
async def sanitize_metadata(
    doc_id: str, session: Session = Depends(db_session)
) -> PatchResponse:
    """Strip risky embedded metadata as a reversible, audited edit."""
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    patch = provenance.sanitize_metadata(doc)
    updated = orchestrator.apply(doc, patch)
    new_version_id = provenance.commit_version(updated, patch=patch)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id

    provenance.record_event(
        doc_id, "metadata.sanitized", actor="api", detail={"patch_id": patch.id}
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=True,
        new_version_id=new_version_id,
        intent=patch.intent,
    )
