"""DocumentOpsAgent workflow planning endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import OpsAgentAction, OpsAgentPlanRequest, OpsAgentPlanResponse
from docos.api.session import Actor, get_actor
from docos.deps import db_session
from docos.services.semantic.agents import plan_document_ops

router = APIRouter(prefix="/documents", tags=["ops-agent"])


@router.post("/{doc_id}/ops-agent/plan", response_model=OpsAgentPlanResponse)
def plan_ops(
    doc_id: str,
    body: OpsAgentPlanRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> OpsAgentPlanResponse:
    """Plan deterministic document workflow actions without mutating the document."""
    _record, doc = _load_latest(session, doc_id, actor)
    plan = plan_document_ops(doc, body.goal, allow_destructive=body.allow_destructive)
    return OpsAgentPlanResponse(
        doc_id=doc_id,
        goal=body.goal,
        classification=plan.classification,
        actions=[OpsAgentAction(**a.model_dump()) for a in plan.actions],
        warnings=plan.warnings,
    )
