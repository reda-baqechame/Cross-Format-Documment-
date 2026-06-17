"""Approval-workflow logic — ordered, multi-party sign-off over a document.

Pure functions over a list of "steps" (anything exposing ``approver``, ``order_index``,
``status``, ``ordered``). The route owns persistence; this module owns the rules:
what the overall state is, and who may act next. Keeping the rules pure makes the
ordered/parallel signing semantics unit-testable without a database.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"


class Step(Protocol):
    approver: str
    order_index: int
    status: str
    ordered: bool


class StepView(BaseModel):
    approver: str
    order_index: int
    status: str
    note: str | None = None


class WorkflowStatus(BaseModel):
    doc_id: str
    workflow_id: str | None
    state: str  # none | in_progress | approved | rejected
    ordered: bool
    steps: list[StepView]
    current_approvers: list[str]  # who may act now (empty when finished)


def overall_state(steps: list[Step]) -> str:
    if not steps:
        return "none"
    if any(s.status == REJECTED for s in steps):
        return "rejected"
    if all(s.status == APPROVED for s in steps):
        return "approved"
    return "in_progress"


def actionable_approvers(steps: list[Step]) -> list[str]:
    """Approvers whose decision is needed now.

    For an ordered workflow that's only the next pending step (by ``order_index``);
    for a parallel workflow it's every still-pending approver. Empty once finished.
    """
    if overall_state(steps) in ("none", "approved", "rejected"):
        return []
    pending = [s for s in steps if s.status == PENDING]
    if not pending:
        return []
    if steps[0].ordered:
        nxt = min(s.order_index for s in pending)
        return [s.approver for s in pending if s.order_index == nxt]
    return [s.approver for s in pending]


def can_act(steps: list[Step], approver: str) -> bool:
    return approver in actionable_approvers(steps)
