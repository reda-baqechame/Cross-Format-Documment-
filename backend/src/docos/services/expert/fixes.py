"""Turn deterministic findings into reversible fix plans.

A finding with ``fix_available=True`` can be converted here into a ``FixPlan``: a list of
``ReversiblePatch`` drafts plus the target document. The plan is *proposed* only — the
packet-audit route applies it explicitly via the same patch pipeline every other edit uses,
so the fix is previewable, undoable, and audited. We never silently mutate a document.

Only deterministic, low-risk fixes are generated automatically (metadata scrub, redact a
cited sensitive span). Anything that requires judgment (rewrite a clause, change a total)
stays a recommended action for a human, never an auto-fix.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from docos.model.patch import Patch, ReversiblePatch
from docos.services.expert.schemas import ExpertFinding


class FixPlan(BaseModel):
    """Proposed reversible patches for one finding against one document.

    ``patches`` are forward ops with empty inverse — the patch pipeline computes the
    exact inverse at apply time (see orchestrator.apply), so callers always get an undo.
    """

    finding_id: str
    document_id: str
    title: str
    patches: list[ReversiblePatch] = Field(default_factory=list)
    auto_fixable: bool = True


def _now() -> datetime:
    return datetime.now(tz=UTC)


def metadata_scrub_fix(finding: ExpertFinding, document_id: str) -> FixPlan:
    """Reversible metadata-sanitize fix for a metadata_leak finding."""
    rp = ReversiblePatch(
        id=f"fix-{finding.id}",
        patches=[Patch(op="sanitize_metadata", target_id=None, payload={})],
        inverse=[],
        intent=f"Scrub leaked metadata flagged by rule {finding.rule_code}",
        created_by="expert-fixes",
        created_at=_now(),
    )
    return FixPlan(
        finding_id=finding.id,
        document_id=document_id,
        title="Remove leaked document metadata",
        patches=[rp],
    )


def redact_span_fix(finding: ExpertFinding, document_id: str) -> FixPlan | None:
    """Reversible redaction fix for a cited sensitive span, one patch per evidence ref."""
    patches: list[ReversiblePatch] = []
    for ev in finding.evidence:
        if not ev.node_id:
            continue
        patches.append(
            ReversiblePatch(
                id=f"fix-{finding.id}-{ev.node_id}",
                patches=[Patch(op="redact", target_id=ev.node_id, payload={})],
                inverse=[],
                intent=f"Redact sensitive span flagged by rule {finding.rule_code}",
                created_by="expert-fixes",
                created_at=_now(),
            )
        )
    if not patches:
        return None
    return FixPlan(
        finding_id=finding.id,
        document_id=document_id,
        title="Redact cited sensitive data",
        patches=patches,
    )


def fix_for(finding: ExpertFinding, document_id: str) -> FixPlan | None:
    """Dispatch on finding type to the right deterministic fix, or None if not auto-fixable."""
    if not finding.fix_available:
        return None
    if finding.type in {"metadata_risk"}:
        return metadata_scrub_fix(finding, document_id)
    if finding.type in {"redaction_risk"}:
        return redact_span_fix(finding, document_id)
    return None
