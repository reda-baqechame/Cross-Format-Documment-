"""DocumentOps run — one call that turns a set of documents into findings + a generated deliverable.

`POST /documentops/run` orchestrates classify → pack-compare → synthesize and records a queryable
audit trail; `GET /documentops/runs/{run_id}` replays it. Read-only and owner-scoped: the run never
mutates source documents — any commit/route/send comes back as an approval-gated action. The
generated report itself is downloaded from `POST /packs/{pack}/report?format=…`.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.db.models import AuditEvent
from docos.deps import db_session, get_provenance
from docos.services.workflows.runner import RunResult, run_documentops

router = APIRouter(prefix="/documentops", tags=["documentops"])

_ACTION = "documentops_run"


class DocumentOpsRunRequest(BaseModel):
    doc_ids: list[str] | None = None  # None ⇒ run across every owned document
    pack: str | None = None  # None ⇒ infer from the documents' classifications


def _actor_label(actor: Actor) -> str:
    return actor.user_id or actor.session_id or "anonymous"


@router.post("/run", response_model=RunResult)
def documentops_run(
    body: DocumentOpsRunRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RunResult:
    """Run the read+generate pipeline over the caller's documents and record the trail."""
    corpus = load_corpus(
        session, body.doc_ids, owner_session_id=actor.session_id, owner_user_id=actor.user_id
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="no matching documents found")

    run_id = uuid4().hex
    try:
        result = run_documentops(
            run_id, [(c.doc_id, c.title, c.doc) for c in corpus], pack=body.pack
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    get_provenance(session).record_event(
        None,
        _ACTION,
        actor=_actor_label(actor),
        detail={
            "run_id": run_id,
            "owner_session_id": actor.session_id,
            "owner_user_id": actor.user_id,
            "result": result.model_dump(),
        },
    )
    session.commit()
    return result


def _owner_ok(detail: dict, actor: Actor) -> bool:
    """A run is visible only to the owner that created it (unguessable id + owner match)."""
    return (
        detail.get("owner_session_id") == actor.session_id
        and detail.get("owner_user_id") == actor.user_id
    )


@router.get("/runs/{run_id}", response_model=RunResult)
def get_documentops_run(
    run_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RunResult:
    """Replay a recorded run (its findings, steps, and proposed next actions)."""
    rows = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == _ACTION)
        .order_by(AuditEvent.created_at.desc())
        .limit(1000)
    ).all()
    for row in rows:
        detail = row.detail or {}
        if detail.get("run_id") == run_id and _owner_ok(detail, actor):
            return RunResult(**detail["result"])
    raise HTTPException(status_code=404, detail="run not found")
