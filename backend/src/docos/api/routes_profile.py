"""Fill Once — a reusable autofill profile.

A user saves their common answers (name, email, address, EIN…) once; any later form's matching
fields auto-populate. The profile is keyed to the caller's session, the same anonymous-owner model
as documents and templates. Filling is an ordinary reversible ``update_node`` per field, so it's
versioned and audited like every other edit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.routes_documents import _load_latest
from docos.api.schemas import AutofillResponse, FillProfileResponse, SaveFillProfileRequest
from docos.api.session import Actor, get_actor
from docos.db.models import FillProfile
from docos.deps import db_session
from docos.model.ids import new_node_id, new_patch_id
from docos.model.patch import Patch, ReversiblePatch

router = APIRouter(tags=["profile"])


def _load_profile(session: Session, actor: Actor) -> FillProfile | None:
    clauses = [FillProfile.owner_session_id == actor.session_id]
    if actor.user_id is not None:
        clauses.append(FillProfile.owner_user_id == actor.user_id)
    for clause in clauses:
        row = session.execute(select(FillProfile).where(clause)).scalars().first()
        if row is not None:
            return row
    return None


@router.get("/fill-profile", response_model=FillProfileResponse)
def get_fill_profile(
    session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> FillProfileResponse:
    row = _load_profile(session, actor)
    return FillProfileResponse(data=dict(row.data) if row else {})


@router.put("/fill-profile", response_model=FillProfileResponse)
def save_fill_profile(
    body: SaveFillProfileRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> FillProfileResponse:
    # Normalise keys to lowercase so matching is case-insensitive against field names.
    data = {k.strip().lower(): v for k, v in body.data.items() if k.strip()}
    row = _load_profile(session, actor)
    if row is None:
        row = FillProfile(
            id=new_node_id("profile"),
            owner_session_id=actor.session_id,
            owner_user_id=actor.user_id,
            data=data,
        )
        session.add(row)
    else:
        row.data = data
        row.updated_at = datetime.now(UTC)
    session.commit()
    return FillProfileResponse(data=data)


@router.post("/documents/{doc_id}/autofill", response_model=AutofillResponse)
def autofill_document(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> AutofillResponse:
    """Fill every blank field whose name matches a saved profile key."""
    _record, doc = _load_latest(session, doc_id, actor)
    row = _load_profile(session, actor)
    profile = dict(row.data) if row else {}

    ops: list[Patch] = []
    for node in doc.nodes.values():
        if node.type != "field":
            continue
        value = getattr(node, "value", None)
        if value is not None and str(value).strip():
            continue  # already filled — never overwrite
        key = (getattr(node, "field_name", "") or "").strip().lower()
        if key and key in profile:
            ops.append(Patch(op="update_node", target_id=node.id, payload={"value": profile[key]}))

    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent=f"autofill {len(ops)} field(s) from profile",
        created_at=datetime.now(UTC),
    )
    new_version_id, _updated = apply_and_commit(
        session, doc_id, doc, patch, event="fields.autofilled", detail={"filled": len(ops)}
    )
    return AutofillResponse(doc_id=doc_id, filled=len(ops), new_version_id=new_version_id)
