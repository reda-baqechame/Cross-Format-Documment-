"""Track-changes / suggest mode.

A *suggestion* is a proposed :class:`ReversiblePatch` that is stored but **not applied**,
so reviewing it never changes the document. Accepting a suggestion runs its ops through
the same apply → commit_version → audit path as any edit (so it is versioned and
undoable); rejecting it just records the decision. This gives Word-style "suggest mode"
on top of the canonical model without a separate edit engine.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import PatchOpDTO
from docos.db.models import Document, SuggestedEdit
from docos.deps import db_session, get_orchestrator, get_provenance
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch

router = APIRouter(prefix="/documents", tags=["suggestions"])

# Ops that act on an existing node and therefore require a valid ``target_id``.
_TARGETED_OPS = frozenset(
    {"set_text", "update_node", "retag", "redact", "unredact", "remove_node", "move_node"}
)


class SuggestRequest(BaseModel):
    ops: list[PatchOpDTO]
    intent: str | None = None
    author: str | None = None


class SuggestionView(BaseModel):
    id: str
    doc_id: str
    author: str | None
    intent: str | None
    status: str  # pending | accepted | rejected
    op_count: int
    new_version_id: str | None
    created_at: str
    decided_at: str | None


class SuggestionListResponse(BaseModel):
    doc_id: str
    suggestions: list[SuggestionView]


def _view(s: SuggestedEdit) -> SuggestionView:
    return SuggestionView(
        id=s.id,
        doc_id=s.document_id,
        author=s.author,
        intent=s.intent,
        status=s.status,
        op_count=len(s.patch.get("patches", [])),
        new_version_id=s.new_version_id,
        created_at=s.created_at.isoformat(),
        decided_at=s.decided_at.isoformat() if s.decided_at else None,
    )


def _require_doc(session: Session, doc_id: str) -> None:
    if session.get(Document, doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")


@router.get("/{doc_id}/suggestions", response_model=SuggestionListResponse)
def list_suggestions(
    doc_id: str, status: str | None = None, session: Session = Depends(db_session)
) -> SuggestionListResponse:
    _require_doc(session, doc_id)
    stmt = select(SuggestedEdit).where(SuggestedEdit.document_id == doc_id)
    if status:
        stmt = stmt.where(SuggestedEdit.status == status)
    rows = session.scalars(stmt.order_by(SuggestedEdit.created_at)).all()
    return SuggestionListResponse(doc_id=doc_id, suggestions=[_view(s) for s in rows])


@router.post("/{doc_id}/suggestions", response_model=SuggestionView)
def create_suggestion(
    doc_id: str, body: SuggestRequest, session: Session = Depends(db_session)
) -> SuggestionView:
    _record, doc = _load_latest(session, doc_id)
    if not body.ops:
        raise HTTPException(status_code=422, detail="at least one op is required")
    for op in body.ops:
        if op.op in _TARGETED_OPS and (op.target_id is None or op.target_id not in doc.nodes):
            raise HTTPException(status_code=422, detail=f"unknown target_id for op '{op.op}'")

    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op=o.op, target_id=o.target_id, payload=o.payload) for o in body.ops],
        inverse=[],
        intent=body.intent,
        created_by=body.author or "system",
        created_at=datetime.now(UTC),
    )
    suggestion = SuggestedEdit(
        id=f"sug_{uuid.uuid4().hex[:12]}",
        document_id=doc_id,
        author=body.author,
        intent=body.intent,
        patch=patch.model_dump(mode="json"),
        status="pending",
    )
    session.add(suggestion)
    get_provenance(session).record_event(
        doc_id,
        "suggestion.created",
        actor=body.author or "api",
        detail={"suggestion_id": suggestion.id, "ops": len(body.ops)},
    )
    session.commit()
    return _view(suggestion)


def _load_pending(session: Session, doc_id: str, sid: str) -> SuggestedEdit:
    _require_doc(session, doc_id)
    suggestion = session.get(SuggestedEdit, sid)
    if suggestion is None or suggestion.document_id != doc_id:
        raise HTTPException(status_code=404, detail="suggestion not found")
    if suggestion.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"suggestion already {suggestion.status}"
        )
    return suggestion


@router.post("/{doc_id}/suggestions/{sid}/accept", response_model=SuggestionView)
def accept_suggestion(
    doc_id: str, sid: str, session: Session = Depends(db_session)
) -> SuggestionView:
    suggestion = _load_pending(session, doc_id, sid)
    _record, doc = _load_latest(session, doc_id)

    patch = ReversiblePatch.model_validate(suggestion.patch)
    # Re-validate targets against the *current* model — the document may have moved on.
    for op in patch.patches:
        if op.op in _TARGETED_OPS and (op.target_id is None or op.target_id not in doc.nodes):
            raise HTTPException(
                status_code=409,
                detail="suggestion no longer applies (a target node is gone)",
            )

    orchestrator = get_orchestrator()
    provenance = get_provenance(session)
    updated = orchestrator.apply(doc, patch)
    new_version_id = provenance.commit_version(updated, patch=patch)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id

    suggestion.status = "accepted"
    suggestion.new_version_id = new_version_id
    suggestion.decided_at = datetime.now(UTC)
    provenance.record_event(
        doc_id,
        "suggestion.accepted",
        actor="api",
        detail={"suggestion_id": sid, "patch_id": patch.id, "version": new_version_id},
    )
    session.commit()
    return _view(suggestion)


@router.post("/{doc_id}/suggestions/{sid}/reject", response_model=SuggestionView)
def reject_suggestion(
    doc_id: str, sid: str, session: Session = Depends(db_session)
) -> SuggestionView:
    suggestion = _load_pending(session, doc_id, sid)
    suggestion.status = "rejected"
    suggestion.decided_at = datetime.now(UTC)
    get_provenance(session).record_event(
        doc_id, "suggestion.rejected", actor="api", detail={"suggestion_id": sid}
    )
    session.commit()
    return _view(suggestion)
