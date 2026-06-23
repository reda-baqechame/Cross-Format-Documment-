"""CLM — clause library + renewal tracking.

A lightweight contract-lifecycle layer over the canonical model: save reusable clauses and insert
them as reversible patches, and track renewal/expiry dates in-app. Everything is session-scoped
(the same anonymous-owner model as documents/templates) and works offline — date suggestions reuse
the deterministic extractor, and reminders are surfaced in-app (no email/push, which needs infra).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    ClauseListResponse,
    ClauseResponse,
    CreateClauseRequest,
    CreateRenewalRequest,
    InsertClauseRequest,
    InsertClauseResponse,
    RenewalListResponse,
    RenewalResponse,
    RenewalSuggestionsResponse,
)
from docos.api.session import Actor, get_actor
from docos.db.models import Clause, RenewalReminder
from docos.deps import db_session
from docos.model.ids import new_node_id, new_patch_id
from docos.model.patch import ReversiblePatch
from docos.services.clm import clauses as clause_svc
from docos.services.clm import renewals as renewal_svc

router = APIRouter(tags=["clm"])


def _owns(model, actor: Actor):
    """Filter clause: rows owned by the caller's session (or user, when registered)."""
    if actor.user_id is not None:
        return model.owner_user_id == actor.user_id
    return model.owner_session_id == actor.session_id


# ── Clause library ──────────────────────────────────────────────────────────────────────────
@router.get("/clauses", response_model=ClauseListResponse)
def list_clauses(
    session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> ClauseListResponse:
    rows = (
        session.execute(select(Clause).where(_owns(Clause, actor)).order_by(Clause.created_at))
        .scalars()
        .all()
    )
    return ClauseListResponse(
        clauses=[
            ClauseResponse(id=r.id, title=r.title, body=r.body, category=r.category) for r in rows
        ]
    )


@router.post("/clauses", response_model=ClauseResponse)
def create_clause(
    body: CreateClauseRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> ClauseResponse:
    row = Clause(
        id=new_node_id("clause"),
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        title=body.title.strip(),
        body=body.body,
        category=(body.category or None),
    )
    session.add(row)
    session.commit()
    return ClauseResponse(id=row.id, title=row.title, body=row.body, category=row.category)


@router.delete("/clauses/{clause_id}", status_code=204)
def delete_clause(
    clause_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> None:
    row = session.get(Clause, clause_id)
    if row is None or (
        row.owner_session_id != actor.session_id
        and (actor.user_id is None or row.owner_user_id != actor.user_id)
    ):
        raise HTTPException(status_code=404, detail="clause not found")
    session.delete(row)
    session.commit()


@router.post("/documents/{doc_id}/insert-clause", response_model=InsertClauseResponse)
def insert_clause(
    doc_id: str,
    body: InsertClauseRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> InsertClauseResponse:
    record, doc = _load_latest(session, doc_id, actor)

    title, text = body.title or "", body.body or ""
    if body.clause_id:
        clause = session.get(Clause, body.clause_id)
        if clause is None or (
            clause.owner_session_id != actor.session_id
            and (actor.user_id is None or clause.owner_user_id != actor.user_id)
        ):
            raise HTTPException(status_code=404, detail="clause not found")
        title, text = clause.title, clause.body
    if not text.strip():
        raise HTTPException(status_code=422, detail="clause body or a clause_id is required")

    ops = clause_svc.build_clause_insert_patches(doc.root_id, title, text)
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent=f"insert clause ({len(ops)} block(s))",
        created_at=datetime.now(UTC),
    )
    new_version_id, _updated = apply_and_commit(
        session, doc_id, doc, patch, event="clause.inserted", detail={"blocks": len(ops)}
    )
    return InsertClauseResponse(doc_id=doc_id, inserted=len(ops), new_version_id=new_version_id)


# ── Renewals ────────────────────────────────────────────────────────────────────────────────
def _renewal_response(row: RenewalReminder) -> RenewalResponse:
    return RenewalResponse(
        id=row.id,
        title=row.title,
        due_date=row.due_date,
        note=row.note,
        status=row.status,
        doc_id=row.doc_id,
        urgency=renewal_svc.urgency(row.due_date),
    )


@router.get("/renewals", response_model=RenewalListResponse)
def list_renewals(
    session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> RenewalListResponse:
    rows = (
        session.execute(
            select(RenewalReminder)
            .where(_owns(RenewalReminder, actor))
            .order_by(RenewalReminder.due_date)
        )
        .scalars()
        .all()
    )
    return RenewalListResponse(renewals=[_renewal_response(r) for r in rows])


@router.post("/renewals", response_model=RenewalResponse)
def create_renewal(
    body: CreateRenewalRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RenewalResponse:
    try:
        date.fromisoformat(body.due_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="due_date must be ISO YYYY-MM-DD") from exc
    row = RenewalReminder(
        id=new_node_id("renewal"),
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        doc_id=body.doc_id,
        title=body.title.strip(),
        due_date=body.due_date,
        note=(body.note or None),
        status="open",
    )
    session.add(row)
    session.commit()
    return _renewal_response(row)


@router.delete("/renewals/{renewal_id}", status_code=204)
def delete_renewal(
    renewal_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> None:
    row = session.get(RenewalReminder, renewal_id)
    if row is None or (
        row.owner_session_id != actor.session_id
        and (actor.user_id is None or row.owner_user_id != actor.user_id)
    ):
        raise HTTPException(status_code=404, detail="renewal not found")
    session.delete(row)
    session.commit()


@router.get("/documents/{doc_id}/renewal-suggestions", response_model=RenewalSuggestionsResponse)
def renewal_suggestions(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RenewalSuggestionsResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    return RenewalSuggestionsResponse(doc_id=doc_id, due_dates=renewal_svc.suggest_due_dates(doc))
