"""AI document-agent endpoint — one natural-language goal -> plan + read results + proposed edits.

Additive: composes existing services (planner, read tools, the edit orchestrator) into a single
transcript. It never commits — proposed edits come back as a preview and are applied only through
the existing ``POST /documents/{id}/patches`` route. Read-only analysis works offline; the modify
step yields an empty proposal when no AI provider is configured.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import AgentRunRequest
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_orchestrator
from docos.services.semantic.agents import AgentRun, run_agent

router = APIRouter(prefix="/documents", tags=["agent"])


@router.post("/{doc_id}/agent", response_model=AgentRun)
async def agent(
    doc_id: str,
    body: AgentRunRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> AgentRun:
    """Run the document agent for a goal.

    Reads execute; edits are proposed (preview) and never committed here — apply them via
    ``POST /documents/{doc_id}/patches`` after review.
    """
    _record, doc = _load_latest(session, doc_id, actor)
    return await run_agent(
        doc, body.goal, orchestrator=get_orchestrator(), allow_destructive=body.allow_destructive
    )
