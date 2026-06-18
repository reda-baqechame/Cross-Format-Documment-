"""Revenue-focused business workflow previews and guarded execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from docos.api.schemas import (
    WorkflowExecuteResponse,
    WorkflowPreset,
    WorkflowStep,
)
from docos.api.session import Actor
from docos.db.models import ApprovalStep, BulkSendPacket, Document
from docos.model.document import CanonicalDocument
from docos.services.collab import approvals
from docos.services.provenance.interface import ProvenancePolicyService
from docos.services.semantic import classify
from docos.services.templates import library


@dataclass(frozen=True)
class StepDef:
    id: str
    label: str
    tool: str
    reason: str
    requires_approval: bool = False
    destructive: bool = False


PRESETS: dict[WorkflowPreset, tuple[StepDef, ...]] = {
    "contract_packet": (
        StepDef(
            "classify_extract",
            "Analyze contract packet",
            "intelligence",
            "Find clauses, parties, dates, and risk signals before routing.",
        ),
        StepDef(
            "prepare_fields",
            "Prepare reusable fields",
            "forms",
            "Detect signature, date, party, and approval fields for repeatable packets.",
        ),
        StepDef(
            "approval_route",
            "Create approval route",
            "approvals",
            "Route legal, finance, and security sign-off before sending.",
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Prove the final packet opens and trust controls survive export.",
        ),
    ),
    "invoice_approval": (
        StepDef(
            "classify_extract",
            "Analyze invoice",
            "intelligence",
            "Extract invoice number, dates, totals, vendor, and mismatch risks.",
        ),
        StepDef(
            "trust_checks",
            "Run trust checks",
            "health",
            "Check metadata, redaction state, accessibility, and seal state.",
        ),
        StepDef(
            "approval_route",
            "Create approval route",
            "approvals",
            "Route finance approval before payment or export.",
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Validate the downloadable finance copy.",
        ),
    ),
    "vendor_onboarding": (
        StepDef(
            "classify_extract",
            "Analyze vendor packet",
            "intelligence",
            "Identify onboarding forms, agreements, policies, and missing data.",
        ),
        StepDef(
            "prepare_fields",
            "Prepare intake fields",
            "forms",
            "Turn blanks into structured fields for vendor completion.",
        ),
        StepDef(
            "approval_route",
            "Create approval route",
            "approvals",
            "Route procurement and security review.",
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Validate a clean packet for the vendor record.",
        ),
    ),
    "employee_form_packet": (
        StepDef(
            "classify_extract",
            "Analyze employee packet",
            "intelligence",
            "Identify intake, consent, checklist, and approval requirements.",
        ),
        StepDef(
            "prepare_fields",
            "Prepare employee fields",
            "forms",
            "Turn HR blanks into required reusable fields.",
        ),
        StepDef(
            "approval_route",
            "Create approval route",
            "approvals",
            "Route HR approval before completion.",
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Validate the final employee packet.",
        ),
    ),
    "proposal_to_signature": (
        StepDef(
            "classify_extract",
            "Analyze proposal or SOW",
            "intelligence",
            "Check scope, pricing, deliverables, timeline, and missing signature needs.",
        ),
        StepDef(
            "prepare_fields",
            "Prepare signature fields",
            "forms",
            "Create signature/date/role fields before sending.",
        ),
        StepDef(
            "approval_route",
            "Create approval route",
            "approvals",
            "Route sales and legal approval before counterparty send.",
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Validate the signature-ready packet.",
        ),
    ),
    "bulk_send_template": (
        StepDef(
            "classify_extract",
            "Analyze template",
            "intelligence",
            "Confirm the source document is suitable for repeated packet creation.",
        ),
        StepDef(
            "prepare_fields",
            "Prepare template variables",
            "forms",
            "Ensure recipient-specific variables are available before sending.",
        ),
        StepDef(
            "bulk_send",
            "Create recipient packets",
            "bulk_send",
            "Create independent recipient copies and approval routes.",
            True,
            True,
        ),
        StepDef(
            "export_validate",
            "Run export validation",
            "export_validation",
            "Validate each generated packet before download or send.",
        ),
    ),
}

LEGAL_SIGN_WARNING = (
    "Integrity seals are not legally binding e-signatures until a regulated signing "
    "provider is configured."
)


def preview_workflow(
    doc_id: str, doc: CanonicalDocument, preset: WorkflowPreset
) -> tuple[str, list[WorkflowStep], list[str]]:
    classification = classify.classify(doc).label
    steps = [_to_step(step) for step in PRESETS[preset]]
    warnings = (
        [LEGAL_SIGN_WARNING]
        if any(s.tool in {"approvals", "bulk_send"} for s in PRESETS[preset])
        else []
    )
    return classification, steps, warnings


def execute_workflow(
    session: Session,
    record: Document,
    doc: CanonicalDocument,
    preset: WorkflowPreset,
    *,
    actor: Actor,
    provenance: ProvenancePolicyService,
    approved_step_ids: set[str],
    confirm_destructive: bool,
    recipients: list[str],
    approvers: list[str],
) -> WorkflowExecuteResponse:
    classification, preview_steps, warnings = preview_workflow(record.id, doc, preset)
    executed: list[WorkflowStep] = []
    skipped: list[WorkflowStep] = []
    next_required: WorkflowStep | None = None

    for step in preview_steps:
        approved = step.id in approved_step_ids
        if step.requires_approval and not approved:
            blocked = step.model_copy(
                update={
                    "status": "blocked",
                    "result": "Explicit approval required before this step can run.",
                }
            )
            skipped.append(blocked)
            if next_required is None:
                next_required = blocked
            continue
        if step.destructive and not confirm_destructive:
            blocked = step.model_copy(
                update={
                    "status": "blocked",
                    "result": "Destructive workflow execution was not confirmed.",
                }
            )
            skipped.append(blocked)
            if next_required is None:
                next_required = blocked
            continue

        result = _execute_step(
            session,
            record,
            doc,
            step,
            actor=actor,
            provenance=provenance,
            recipients=recipients,
            approvers=approvers,
        )
        executed.append(step.model_copy(update={"status": "completed", "result": result}))

    provenance.record_event(
        record.id,
        "workflow.executed",
        actor="api",
        detail={
            "preset": preset,
            "executed": [s.id for s in executed],
            "skipped": [s.id for s in skipped],
        },
    )
    session.commit()
    return WorkflowExecuteResponse(
        doc_id=record.id,
        preset=preset,
        classification=classification,
        executed_steps=executed,
        skipped_steps=skipped,
        next_required_approval=next_required,
        warnings=warnings,
    )


def _to_step(step: StepDef) -> WorkflowStep:
    return WorkflowStep(
        id=step.id,
        label=step.label,
        tool=step.tool,
        requires_approval=step.requires_approval,
        destructive=step.destructive,
        reason=step.reason,
    )


def _execute_step(
    session: Session,
    record: Document,
    doc: CanonicalDocument,
    step: WorkflowStep,
    *,
    actor: Actor,
    provenance: ProvenancePolicyService,
    recipients: list[str],
    approvers: list[str],
) -> str:
    if step.tool in {"intelligence", "health", "forms", "export_validation"}:
        return "Ready in workspace; use the linked panel for detailed results."
    if step.tool == "approvals":
        names = _clean_unique(approvers) or _default_approvers(step.id)
        _start_approval_route(session, record.id, names, provenance)
        return f"Started approval route for {', '.join(names)}."
    if step.tool == "bulk_send":
        names = _clean_unique(recipients)
        if not names:
            return "No recipients supplied; no packets created."
        batch_id = _create_bulk_packets(session, record, doc, names, actor, provenance)
        return f"Created bulk-send batch {batch_id} for {len(names)} recipient(s)."
    return "Step recorded."


def _clean_unique(values: list[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for value in values:
        v = value.strip()
        if v and v not in seen:
            clean.append(v)
            seen.add(v)
    return clean


def _default_approvers(step_id: str) -> list[str]:
    if step_id == "approval_route":
        return ["Legal Review", "Finance Approval"]
    return ["Reviewer"]


def _start_approval_route(
    session: Session, doc_id: str, approvers_: list[str], provenance: ProvenancePolicyService
) -> None:
    existing = list(
        session.query(ApprovalStep)
        .filter(ApprovalStep.document_id == doc_id)
        .order_by(ApprovalStep.order_index)
        .all()
    )
    if approvals.overall_state(existing) == "in_progress":
        raise ValueError("an approval workflow is already in progress")
    for step in existing:
        session.delete(step)
    workflow_id = uuid.uuid4().hex
    for i, approver in enumerate(approvers_):
        session.add(
            ApprovalStep(
                document_id=doc_id,
                workflow_id=workflow_id,
                order_index=i,
                approver=approver,
                ordered=True,
                status=approvals.PENDING,
            )
        )
    provenance.record_event(
        doc_id,
        "workflow.approval_route_created",
        actor="api",
        detail={"workflow_id": workflow_id, "approvers": approvers_},
    )


def _create_bulk_packets(
    session: Session,
    record: Document,
    doc: CanonicalDocument,
    recipients: list[str],
    actor: Actor,
    provenance: ProvenancePolicyService,
) -> str:
    snapshot = library.snapshot(doc)
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    base_title = record.title or record.id
    for recipient in recipients:
        copy = library.instantiate(snapshot, title=f"{base_title} - {recipient}")
        packet_record = Document(
            id=copy.doc_id,
            title=copy.meta.title,
            source_format=copy.meta.source_format,
            source_mime=copy.meta.source_mime,
            blob_key="",
            owner_session_id=actor.session_id,
            owner_user_id=actor.user_id,
        )
        session.add(packet_record)
        session.flush()
        version_id = provenance.commit_version(copy)
        packet_record.current_version_id = version_id
        workflow_id = uuid.uuid4().hex
        session.add(
            ApprovalStep(
                document_id=copy.doc_id,
                workflow_id=workflow_id,
                order_index=0,
                approver=recipient,
                ordered=True,
                status=approvals.PENDING,
            )
        )
        session.add(
            BulkSendPacket(
                batch_id=batch_id,
                source_doc_id=record.id,
                recipient=recipient,
                packet_doc_id=copy.doc_id,
                message="Prepared by guided workflow.",
            )
        )
        provenance.record_event(
            copy.doc_id,
            "workflow.bulk_packet_created",
            actor="api",
            detail={"batch_id": batch_id, "recipient": recipient, "source_doc_id": record.id},
        )
    provenance.record_event(
        record.id,
        "workflow.bulk_send_created",
        actor="api",
        detail={"batch_id": batch_id, "recipients": recipients},
    )
    return batch_id
