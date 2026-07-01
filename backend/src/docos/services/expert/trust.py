"""Trust findings for packet audits — metadata leaks and exposed sensitive data.

Every vertical calls :func:`trust_findings` so packet audits surface fixable trust issues
with cited evidence (or explicit human-review escalation when evidence is absent).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.expert import evidence as ev
from docos.services.expert.rules import new_finding
from docos.services.expert.schemas import EvidenceRef, ExpertFinding
from docos.services.provenance import sensitive
from docos.services.provenance.health import RISKY_META_KEYS

# Business packets contain long numeric IDs (HS codes, invoice numbers) that trip phone heuristics.
_TRUST_CATEGORIES = frozenset({"email", "us_ssn", "credit_card"})


def trust_findings(
    docs: list[tuple[str, str | None, CanonicalDocument]],
) -> list[ExpertFinding]:
    """Scan each packet document for metadata leaks and exposed sensitive spans."""
    out: list[ExpertFinding] = []
    for doc_id, _title, doc in docs:
        out.extend(_metadata_findings(doc_id, doc))
        out.extend(_sensitive_findings(doc_id, doc))
        out.extend(_pending_redaction_findings(doc_id, doc))
    return out


def _metadata_findings(doc_id: str, doc: CanonicalDocument) -> list[ExpertFinding]:
    if doc.redaction.metadata_sanitized:
        return []
    leaked: list[tuple[str, str]] = []
    for key in RISKY_META_KEYS:
        val = doc.meta.custom.get(key)
        if val:
            leaked.append((key, str(val)))
    if not leaked:
        return []
    keys = ", ".join(k for k, _ in leaked)
    return [
        new_finding(
            type_="metadata_risk",
            severity="warning",
            title="Embedded metadata may leak internal information",
            explanation=(
                f"Document metadata contains {keys} before sanitization. "
                "Recipients can read these fields in many viewers."
            ),
            evidence=[
                EvidenceRef(
                    document_id=doc_id,
                    document_type=None,
                    page_number=None,
                    node_id=None,
                    field_name=key,
                    raw_text=f"{key}={val}",
                    normalized_value=val,
                )
                for key, val in leaked
            ],
            business_impact="Internal author names or revision history may be visible to clients.",
            recommended_action="Run metadata sanitization before sending.",
            fix_available=True,
        )
    ]


def _sensitive_findings(doc_id: str, doc: CanonicalDocument) -> list[ExpertFinding]:
    hits = [h for h in sensitive.scan_document(doc) if h.category in _TRUST_CATEGORIES]
    if not hits:
        return []
    evidence: list[EvidenceRef] = []
    for hit in hits:
        if is_redacted(doc, hit.node_id):
            continue
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
    if not evidence:
        return []
    return [
        new_finding(
            type_="redaction_risk",
            severity="blocking",
            title="Sensitive data is exposed in document text",
            explanation=(
                f"{len(evidence)} sensitive span(s) detected and not yet redacted "
                "(email, phone, payment card, etc.)."
            ),
            evidence=evidence,
            business_impact="Sending without redaction may violate privacy or compliance policy.",
            recommended_action="Apply true redaction to cited spans before export.",
            fix_available=True,
        )
    ]


def _pending_redaction_findings(doc_id: str, doc: CanonicalDocument) -> list[ExpertFinding]:
    pending = [nid for nid in doc.redaction.pending if not is_redacted(doc, nid)]
    if not pending:
        return []
    evidence: list[EvidenceRef] = []
    for node_id in pending[:5]:
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
    return [
        new_finding(
            type_="redaction_risk",
            severity="blocking",
            title="Unapplied redactions may still leak content",
            explanation=(
                f"{len(pending)} redaction mark(s) are not yet burned in — hidden text "
                "can still be recovered on export."
            ),
            evidence=evidence,
            business_impact="Recipients may recover text that was visually blacked out.",
            recommended_action="Export or clean the document to apply redactions permanently.",
            fix_available=bool(evidence),
            rule_code="pending_redactions",
        )
    ]
