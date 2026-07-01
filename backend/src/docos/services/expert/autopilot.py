"""DocumentOps Autopilot — outcome orchestration over the expert spine.

Runs Understand → Verify → (optional) Fix → Export → Proof without duplicating readiness,
packet audit, or clean logic. Every step returns a unified ``ResultContract``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services.expert.fixes import FixPlan, fix_for
from docos.services.expert.readiness_bridge import readiness_to_expert_findings
from docos.services.expert.result_contract import from_readiness
from docos.services.expert.schemas import ExpertFinding, ResultContract
from docos.services.provenance import readiness
from docos.services.provenance.diff import diff_documents
from docos.services.semantic import classify as classify_service

AutopilotGoal = Literal["clean_before_send", "review", "export", "compare"]


class AutopilotRunRequest(BaseModel):
    goal: AutopilotGoal = "clean_before_send"
    against_doc_id: str | None = None  # compare goal
    apply_fixes: bool = False


class AutopilotRunResponse(BaseModel):
    doc_id: str
    goal: AutopilotGoal
    result: ResultContract
    fix_plans: list[FixPlan] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    classification: str | None = None
    compare_summary: str | None = None


def _counts(findings: list[ExpertFinding]) -> tuple[int, int]:
    blocking = sum(1 for f in findings if f.severity == "blocking")
    warning = sum(1 for f in findings if f.severity == "warning")
    return blocking, warning


def run(
    doc_id: str,
    doc: CanonicalDocument,
    *,
    goal: AutopilotGoal = "clean_before_send",
    against: CanonicalDocument | None = None,
) -> AutopilotRunResponse:
    """Execute a deterministic autopilot goal (no LLM)."""
    steps: list[str] = []
    report = readiness.build_report(doc)
    findings = readiness_to_expert_findings(doc_id, doc, report)
    result = from_readiness(doc_id, report, findings)
    blocking, warning = _counts(findings)
    result = result.model_copy(
        update={
            "blocking_count": blocking,
            "warning_count": warning,
            "job_type": "clean_before_send" if goal == "clean_before_send" else "patch_apply",
        }
    )
    steps.append("Ran send-ready check")
    classification = classify_service.classify(doc).label
    steps.append(f"Classified as {classification}")

    fix_plans: list[FixPlan] = []
    for f in findings:
        plan = fix_for(f, doc_id)
        if plan:
            fix_plans.append(plan)
    if fix_plans:
        steps.append(f"Planned {len(fix_plans)} reversible fix(es)")

    compare_summary: str | None = None
    if goal == "compare" and against is not None:
        diff = diff_documents(doc, against)
        n = diff.added + diff.removed + diff.changed
        compare_summary = f"{n} block-level change(s) detected"
        steps.append("Compared against reference document")
    elif goal == "export":
        result = result.model_copy(update={"job_type": "export"})
        steps.append("Export validation available via /export")

    if goal == "review":
        steps.append("Review complete — human approval required for ambiguous findings")

    return AutopilotRunResponse(
        doc_id=doc_id,
        goal=goal,
        result=result,
        fix_plans=fix_plans,
        steps=steps,
        classification=classification,
        compare_summary=compare_summary,
    )
