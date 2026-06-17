"""Pure approval-workflow rules: overall state + who may act next."""

from __future__ import annotations

from dataclasses import dataclass

from docos.services.collab import approvals


@dataclass
class FakeStep:
    approver: str
    order_index: int
    status: str
    ordered: bool = True


def steps(*specs, ordered=True):
    return [FakeStep(a, i, s, ordered) for i, (a, s) in enumerate(specs)]


def test_overall_state_transitions():
    assert approvals.overall_state([]) == "none"
    assert approvals.overall_state(steps(("a", "pending"))) == "in_progress"
    assert approvals.overall_state(steps(("a", "approved"), ("b", "approved"))) == "approved"
    assert approvals.overall_state(steps(("a", "approved"), ("b", "rejected"))) == "rejected"


def test_ordered_only_next_approver_can_act():
    s = steps(("alice", "pending"), ("bob", "pending"), ordered=True)
    assert approvals.actionable_approvers(s) == ["alice"]
    assert approvals.can_act(s, "alice")
    assert not approvals.can_act(s, "bob")


def test_ordered_advances_after_approval():
    s = steps(("alice", "approved"), ("bob", "pending"), ordered=True)
    assert approvals.actionable_approvers(s) == ["bob"]


def test_parallel_all_pending_can_act():
    s = steps(("alice", "pending"), ("bob", "pending"), ordered=False)
    assert set(approvals.actionable_approvers(s)) == {"alice", "bob"}


def test_finished_workflow_has_no_actionable():
    assert approvals.actionable_approvers(steps(("a", "approved"))) == []
    assert approvals.actionable_approvers(steps(("a", "rejected"))) == []
