"""Approval / multi-party signing workflows.

Start an ordered (or parallel) sign-off across several approvers; each approves or
rejects in turn. State is tracked in ``approval_steps`` and every transition is written
to the audit log, so the workflow is fully accountable. A rejection halts the workflow.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document
from docos.api.session import Actor, get_actor
from docos.db.models import ApprovalStep
from docos.deps import db_session, get_provenance
from docos.services.collab import approvals

router = APIRouter(prefix="/documents", tags=["approvals"])


class StartWorkflowRequest(BaseModel):
    approvers: list[str]
    ordered: bool = True


class DecisionRequest(BaseModel):
    approver: str
    decision: str  # "approve" | "reject"
    note: str | None = None


def _steps(session: Session, doc_id: str) -> list[ApprovalStep]:
    return list(
        session.scalars(
            select(ApprovalStep)
            .where(ApprovalStep.document_id == doc_id)
            .order_by(ApprovalStep.order_index)
        ).all()
    )


def _status(doc_id: str, steps: list[ApprovalStep]) -> approvals.WorkflowStatus:
    return approvals.WorkflowStatus(
        doc_id=doc_id,
        workflow_id=steps[0].workflow_id if steps else None,
        state=approvals.overall_state(steps),
        ordered=steps[0].ordered if steps else True,
        steps=[
            approvals.StepView(
                approver=s.approver, order_index=s.order_index, status=s.status, note=s.note
            )
            for s in steps
        ],
        current_approvers=approvals.actionable_approvers(steps),
    )


def _require_doc(session: Session, doc_id: str, actor: Actor) -> None:
    get_owned_document(session, doc_id, actor)


@router.get("/{doc_id}/approvals", response_model=approvals.WorkflowStatus)
def get_workflow(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> approvals.WorkflowStatus:
    _require_doc(session, doc_id, actor)
    return _status(doc_id, _steps(session, doc_id))


@router.post("/{doc_id}/approvals", response_model=approvals.WorkflowStatus)
def start_workflow(
    doc_id: str,
    body: StartWorkflowRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> approvals.WorkflowStatus:
    _require_doc(session, doc_id, actor)
    names = [a.strip() for a in body.approvers if a.strip()]
    if not names:
        raise HTTPException(status_code=422, detail="at least one approver is required")

    existing = _steps(session, doc_id)
    if approvals.overall_state(existing) == "in_progress":
        raise HTTPException(status_code=409, detail="an approval workflow is already in progress")

    # Clear any finished prior workflow so a document can be re-routed for approval.
    for step in existing:
        session.delete(step)

    workflow_id = uuid.uuid4().hex
    for i, approver in enumerate(names):
        session.add(
            ApprovalStep(
                document_id=doc_id,
                workflow_id=workflow_id,
                order_index=i,
                approver=approver,
                ordered=body.ordered,
                status=approvals.PENDING,
            )
        )
    get_provenance(session).record_event(
        doc_id,
        "approval.started",
        actor="api",
        detail={"workflow_id": workflow_id, "approvers": names, "ordered": body.ordered},
    )
    session.commit()
    return _status(doc_id, _steps(session, doc_id))


@router.post("/{doc_id}/approvals/decision", response_model=approvals.WorkflowStatus)
def decide(
    doc_id: str,
    body: DecisionRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> approvals.WorkflowStatus:
    _require_doc(session, doc_id, actor)
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'")

    steps = _steps(session, doc_id)
    if approvals.overall_state(steps) in ("none", "approved", "rejected"):
        raise HTTPException(status_code=409, detail="no approval workflow is awaiting a decision")

    approver = body.approver.strip()
    if not approvals.can_act(steps, approver):
        raise HTTPException(
            status_code=409,
            detail=f"it is not {approver or 'this approver'}'s turn to decide",
        )

    step = next(s for s in steps if s.approver == approver and s.status == approvals.PENDING)
    step.status = approvals.APPROVED if body.decision == "approve" else approvals.REJECTED
    step.note = body.note
    step.decided_at = datetime.now(UTC)

    get_provenance(session).record_event(
        doc_id,
        f"approval.{step.status}",
        actor="api",
        detail={"workflow_id": step.workflow_id, "approver": approver, "note": body.note},
    )
    session.commit()

    steps = _steps(session, doc_id)
    final = approvals.overall_state(steps)
    if final in ("approved", "rejected"):
        get_provenance(session).record_event(
            doc_id,
            f"approval.workflow_{final}",
            actor="api",
            detail={"workflow_id": steps[0].workflow_id},
        )
        session.commit()
    return _status(doc_id, steps)
