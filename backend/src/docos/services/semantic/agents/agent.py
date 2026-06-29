"""The agentic document brain — one natural-language goal → plan → run tools → propose changes.

This unifies the deterministic planner (``plan_document_ops``) with the LLM edit orchestrator
(``orchestrator.interpret``) and the read services (classify/extract/intelligence/sensitive) into a
single transcript the UI can render and the user can approve.

Safety + honesty (unchanged invariants):
* Read tools run deterministically and offline (no LLM needed).
* The modify step only *proposes* a reversible patch with a before/after **preview** — it is never
  committed here. Committing still goes through the existing ``POST /documents/{id}/patches`` path
  (preview → approve → commit → audit). So the agent can't silently mutate a document.
* With ``LLM_PROVIDER=noop`` the modify step yields an empty proposal (honest), and the rest of the
  transcript (plan + read results + recommendations) is fully populated.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.semantic import preview as preview_service
from docos.services.semantic.agents import tools as toolbox
from docos.services.semantic.agents.document_ops import plan_document_ops
from docos.services.semantic.interface import SemanticOrchestrator
from docos.services.semantic.preview import PatchPreview
from docos.services.semantic.skills import autopilot

# Goal keywords that imply the user wants the document changed (vs. just read/analyzed).
_MODIFY_TERMS = (
    "edit", "change", "fix", "replace", "rewrite", "update", "set ", "correct",
    "redact", "remove", "delete", "clean", "sanitize", "fill",
)

# Goal keywords that imply a domain review/validation (pull in the matching business pack).
_REVIEW_TERMS = (
    "review", "validate", "check", "risk", "contract", "onboard", "compliance", "audit",
)


class AgentStep(BaseModel):
    tool: str
    kind: str  # read | mutate | action
    label: str
    status: str  # done | proposed | requires_approval | skipped
    summary: str
    data: dict = {}
    requires_approval: bool = False
    destructive: bool = False


class RecommendedAction(BaseModel):
    kind: str
    label: str
    params: dict = {}


class AgentRun(BaseModel):
    goal: str
    classification: str
    used_llm: bool
    steps: list[AgentStep]
    proposed_patch: PatchPreview | None = None
    recommended_actions: list[RecommendedAction]
    warnings: list[str]
    # Set by the iterative agent loop (executor.py); the deterministic path leaves them empty.
    answer: str = ""
    citations: list[dict] = []
    # Tallied token usage across the loop's LLM turns, when the provider reports it (else None).
    usage: dict | None = None


def _wants_modification(goal: str) -> bool:
    g = goal.lower()
    return any(term in g for term in _MODIFY_TERMS)


def _recommended(doc: CanonicalDocument) -> list[RecommendedAction]:
    report = autopilot.analyze(doc)
    out: list[RecommendedAction] = []
    for action in getattr(report, "actions", []) or []:
        out.append(
            RecommendedAction(
                kind=getattr(action, "kind", "navigate"),
                label=getattr(action, "label", ""),
                params=getattr(action, "params", {}) or {},
            )
        )
    return out


async def run_agent(
    doc: CanonicalDocument,
    goal: str,
    *,
    orchestrator: SemanticOrchestrator,
    allow_destructive: bool = False,
) -> AgentRun:
    """Plan the goal, execute the relevant read tools, and (if the goal implies a change) propose a
    reversible patch preview. Never commits."""
    plan = plan_document_ops(doc, goal, allow_destructive=allow_destructive)
    steps: list[AgentStep] = []
    used_llm = False

    # Map planned tool names to registered read tools; run the deterministic ones.
    planned = [a.tool for a in plan.actions]
    # Always ground the transcript with classify + extract; add intelligence; add sensitive on a
    # redaction/clean intent.
    read_sequence = ["classify", "extract", "intelligence"]
    if any(t in ("redact",) for t in planned) or "redact" in goal.lower() or "pii" in goal.lower():
        read_sequence.append("sensitive_scan")
    # A review/validation intent pulls in the matching business pack (it self-skips when none fits).
    if any(t in goal.lower() for t in _REVIEW_TERMS):
        read_sequence.append("pack_review")

    for name in read_sequence:
        tool = toolbox.get_tool(name)
        if tool is None or tool.run is None:
            continue
        result = tool.run(doc)
        steps.append(
            AgentStep(
                tool=tool.name, kind=tool.kind, label=tool.label, status="done",
                summary=result.summary, data=result.data,
            )
        )

    proposed: PatchPreview | None = None
    if _wants_modification(goal):
        # The model proposes ops; offline noop yields an empty patch (honest no-op).
        patch = await orchestrator.interpret(doc, goal)
        used_llm = bool(patch.patches)
        proposed = preview_service.build_preview(doc, patch.patches)
        steps.append(
            AgentStep(
                tool="modify", kind="mutate", label="Propose edits",
                status="proposed" if patch.patches else "skipped",
                summary=(
                    f"Proposed {proposed.change_count} reversible change(s) — preview shown, "
                    "approval required before commit."
                    if patch.patches
                    else "No edits proposed (no AI provider configured, or none applicable)."
                ),
                requires_approval=True,
            )
        )

    # Carry the plan's approval-gated action steps (export/route) as transcript entries.
    for action in plan.actions:
        if action.tool in ("approval-route", "export"):
            steps.append(
                AgentStep(
                    tool=action.tool, kind="action", label=action.label,
                    status="requires_approval" if action.requires_approval else "proposed",
                    summary=action.reason,
                    requires_approval=action.requires_approval,
                    destructive=action.destructive,
                )
            )

    return AgentRun(
        goal=goal,
        classification=plan.classification,
        used_llm=used_llm,
        steps=steps,
        proposed_patch=proposed,
        recommended_actions=_recommended(doc),
        warnings=plan.warnings,
    )
