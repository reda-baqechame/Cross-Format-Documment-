"""Map single-document readiness checks to ExpertFinding-shaped items."""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.expert import evidence as ev
from docos.services.expert.rules import new_finding
from docos.services.expert.schemas import EvidenceRef, ExpertFinding
from docos.services.provenance import sensitive
from docos.services.provenance.readiness import (
    FIX_REDACT_PII,
    FIX_SANITIZE_METADATA,
    ReadinessReport,
)

_STATUS_TO_SEVERITY = {"pass": "info", "warn": "warning", "fail": "blocking"}
_TYPE_FOR_CHECK = {
    "exposed_pii": "redaction_risk",
    "hidden_metadata": "metadata_risk",
    "pending_redactions": "redaction_risk",
}


def readiness_to_expert_findings(
    doc_id: str,
    doc: CanonicalDocument,
    report: ReadinessReport,
) -> list[ExpertFinding]:
    """Convert non-pass readiness checks into evidence-bound expert findings."""
    findings: list[ExpertFinding] = []
    pii_by_node = {h.node_id: h for h in sensitive.scan_document(doc)}
    for i, check in enumerate(report.checks):
        if check.status == "pass":
            continue
        evidence: list[EvidenceRef] = []
        if check.id == "exposed_pii":
            for hit in pii_by_node.values():
                span = next((s for s in ev.sourced_spans(doc) if s.node_id == hit.node_id), None)
                evidence.append(
                    EvidenceRef(
                        document_id=doc_id,
                        document_type=None,
                        page_number=span.page_number if span else None,
                        node_id=hit.node_id,
                        field_name=hit.category,
                        raw_text=span.raw_text if span else hit.excerpt,
                        normalized_value=hit.label,
                    )
                )
        elif check.id == "hidden_metadata":
            for key in ("author", "last_modified_by", "comments", "revision"):
                val = doc.meta.custom.get(key)
                if val:
                    evidence.append(
                        EvidenceRef(
                            document_id=doc_id,
                            document_type=None,
                            field_name=key,
                            raw_text=f"{key}={val}",
                            normalized_value=str(val),
                        )
                    )
        elif check.id == "pending_redactions":
            for node_id in doc.redaction.pending[:5]:
                span = next((s for s in ev.sourced_spans(doc) if s.node_id == node_id), None)
                evidence.append(
                    EvidenceRef(
                        document_id=doc_id,
                        document_type=None,
                        page_number=span.page_number if span else None,
                        node_id=node_id,
                        field_name="pending_redaction",
                        raw_text=span.raw_text if span else f"node:{node_id}",
                    )
                )
        fix_available = check.fixable and check.fix_action in {
            FIX_SANITIZE_METADATA,
            FIX_REDACT_PII,
        }
        human = check.status != "fail" and not evidence and check.id != "unfilled_fields"
        findings.append(
            new_finding(
                type_=_TYPE_FOR_CHECK.get(check.id, "compliance_risk"),
                severity=_STATUS_TO_SEVERITY[check.status],
                title=check.label,
                explanation=check.detail,
                evidence=evidence,
                recommended_action=check.fix_action or "Review before sending.",
                human_review_required=human,
                fix_available=fix_available,
            ).model_copy(update={"id": f"readiness-{check.id}-{i}", "rule_code": check.id})
        )
    return findings
