"""DocumentOpsAgent planning layer.

The first version is deterministic and approval-gated. It can later be wrapped by the
OpenAI Agents SDK, but the tool contract is already explicit: classify, extract, validate,
redact, template-fill, approval-route, and export are separate actions with destructive
actions marked for human approval.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.semantic import classify


class PlannedAction(BaseModel):
    tool: str
    label: str
    destructive: bool = False
    requires_approval: bool = False
    reason: str


class DocumentOpsPlan(BaseModel):
    classification: str
    actions: list[PlannedAction]
    warnings: list[str]


def plan_document_ops(
    doc: CanonicalDocument, goal: str, *, allow_destructive: bool
) -> DocumentOpsPlan:
    goal_l = goal.lower()
    classification = classify.classify(doc).label
    warnings: list[str] = []
    actions: list[PlannedAction] = [
        PlannedAction(
            tool="classify",
            label="Classify document",
            reason="Identify the document workflow before routing actions.",
        ),
        PlannedAction(
            tool="extract",
            label="Extract key fields",
            reason="Pull dates, money, contacts, and label/value fields for validation.",
        ),
        PlannedAction(
            tool="validate",
            label="Run export validation",
            reason="Prove the output opens and trust controls are preserved.",
        ),
    ]

    if any(term in goal_l for term in ("form", "template", "packet", "onboarding")):
        actions.append(
            PlannedAction(
                tool="template-fill",
                label="Detect blanks and prepare reusable fields",
                reason="Business document packets depend on reliable variables and field metadata.",
            )
        )

    if any(term in goal_l for term in ("approve", "approval", "send", "sign", "signature")):
        actions.append(
            PlannedAction(
                tool="approval-route",
                label="Prepare approval route",
                requires_approval=True,
                reason=(
                    "Routing documents to people is a workflow side effect and must be confirmed."
                ),
            )
        )
        warnings.append(
            "Integrity seals are not legally binding e-signatures until a regulated signing "
            "provider is configured."
        )

    if any(term in goal_l for term in ("redact", "clean", "safe", "privacy", "pii", "secret")):
        actions.append(
            PlannedAction(
                tool="redact",
                label="Scan and redact sensitive data",
                destructive=True,
                requires_approval=True,
                reason=(
                    "Redaction changes document content and must stay explicitly approval-gated."
                ),
            )
        )

    if any(term in goal_l for term in ("export", "download", "pdf", "docx", "xlsx", "pptx")):
        actions.append(
            PlannedAction(
                tool="export",
                label="Export requested format",
                reason="Deliver a file only after validation reports no blocking failures.",
            )
        )

    if not allow_destructive and any(a.destructive for a in actions):
        warnings.append(
            "Destructive actions are planned only; pass explicit approval before execution."
        )

    return DocumentOpsPlan(classification=classification, actions=actions, warnings=warnings)
