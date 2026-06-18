"""Autopilot — assemble a document into a typed object: type, key facts, checks, next actions.

This is the "what should happen next" answer the market rewards: classify → extract typed fields
→ validate → flag what needs human review (exception-first) → recommend the next action. Pure,
deterministic, offline; LLM enhancement can layer on later without changing the contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import (
    ExtractedField,
    RecommendedAction,
    SkillFinding,
)
from docos.services.semantic.skills.generic import GenericSkill
from docos.services.semantic.skills.registry import select_skill
from docos.services.semantic.skills.taxonomy import CATEGORY_LABELS


class AutopilotReport(BaseModel):
    category: str  # human label, e.g. "Financial"
    type: str  # human label, e.g. "Invoice"
    type_id: str
    type_confidence: float
    skill_label: str  # "invoice" | "contract" | … (generic uses the detected type id)
    title: str
    deep: bool  # True when a purpose-specific deep skill handled it
    fields: list[ExtractedField] = Field(default_factory=list)
    findings: list[SkillFinding] = Field(default_factory=list)
    actions: list[RecommendedAction] = Field(default_factory=list)
    needs_review: bool = False


def analyze(doc: CanonicalDocument) -> AutopilotReport:
    skill, dt, confidence, _signals = select_skill(doc)
    fields = skill.extract(doc)
    findings = skill.check(doc, fields)
    actions = skill.recommend(doc, fields, findings)

    needs_review = any(f.level == "fail" for f in findings) or any(
        f.name in skill.required_fields and f.status != "found" for f in fields
    )

    category_label = CATEGORY_LABELS.get(skill.category, "Other")
    type_label = dt.label if dt is not None else "Unrecognized"
    type_id = dt.id if dt is not None else "unknown"

    return AutopilotReport(
        category=category_label,
        type=type_label,
        type_id=type_id,
        type_confidence=confidence,
        skill_label=skill.label,
        title=skill.title,
        deep=not isinstance(skill, GenericSkill),
        fields=fields,
        findings=findings,
        actions=actions,
        needs_review=needs_review,
    )
