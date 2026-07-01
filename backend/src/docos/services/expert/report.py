"""Report assembly — combine facts, findings, and summaries into one ExpertReport.

This is the single function a packet-audit route calls. It runs the pack's registered
rules over the packet context, derives the verdict/score deterministically, and emits the
executive summary in business language (offline; the optional judge can rewrite it when a
provider is configured).
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument
from docos.services.expert.fact_graph import FactGraph
from docos.services.expert.rules import PacketContext, RuleRegistry
from docos.services.expert.schemas import (
    AuditSummary,
    DocumentSummary,
    ExpertFinding,
    ExpertReport,
    ExportSummary,
    MissingDocument,
    RecommendedAction,
    RedactionSummary,
)
from docos.services.expert.scoring import readiness_score, verdict_from
from docos.services.expert.trust import trust_findings


def _executive_summary(
    pack: str,
    verdict: str,
    score: float,
    findings: list[ExpertFinding],
    missing: list[MissingDocument],
    doc_count: int,
) -> str:
    blocking = [f for f in findings if f.severity == "blocking"]
    warnings = [f for f in findings if f.severity == "warning"]
    info = [f for f in findings if f.severity == "info"]
    missing_count = len(missing)
    if verdict == "blocked":
        head = (
            f"BLOCKED — {len(blocking)} blocking issue(s)"
            f"{f', {len(warnings)} warning(s)' if warnings else ''}"
            f" across {doc_count} document(s)."
        )
    elif verdict == "needs_review":
        head = (
            f"NEEDS REVIEW — {len(warnings)} warning(s)"
            f"{f', {missing_count} missing document(s)' if missing_count else ''}"
            f" across {doc_count} document(s)."
        )
    else:
        head = f"READY — packet is consistent across {doc_count} document(s)."
    if missing_count:
        head += f" Missing: {', '.join(m.label for m in missing)}."
    if info:
        head += f" {len(info)} informational note(s)."
    head += f" Readiness score: {score:.0%}."
    return head


def _recommended_actions(findings: list[ExpertFinding]) -> list[RecommendedAction]:
    """One action per blocking/warning finding that has a recommended_action."""
    out: list[RecommendedAction] = []
    for f in findings:
        if f.severity == "info" or not f.recommended_action:
            continue
        out.append(
            RecommendedAction(
                title=f.title,
                detail=f.recommended_action,
                severity=f.severity,  # type: ignore[arg-type]
                related_findings=[f.id],
                auto_fixable=f.fix_available,
            )
        )
    return out


def build_report(
    *,
    packet_id: str,
    pack: str,
    documents: list[DocumentSummary],
    facts: FactGraph,
    registry: RuleRegistry,
    context_extra: dict | None = None,
    missing_documents: list[MissingDocument] | None = None,
    redaction_summary: RedactionSummary | None = None,
    export_summary=None,
    model_versions: dict[str, str] | None = None,
    raw_docs: list[tuple[str, str | None, CanonicalDocument]] | None = None,
) -> ExpertReport:
    """Run the registry over the packet and assemble the ExpertReport."""
    ctx = PacketContext(
        packet_id=packet_id,
        pack=pack,
        documents=documents,
        facts=facts,
        required_documents=missing_documents or [],
    )
    findings = registry.run(ctx)
    if raw_docs:
        trust = trust_findings(raw_docs)
        for i, f in enumerate(trust):
            if not f.id:
                f = f.model_copy(update={"id": f"trust-{i}"})
            if f.rule_code is None:
                code = "metadata_leak" if f.type == "metadata_risk" else "sensitive_exposed"
                f = f.model_copy(update={"rule_code": code})
            findings.append(f)
    verdict = verdict_from(findings)
    score = readiness_score(findings)
    extracted = [f.field_ref for f in facts.facts]
    required = missing_documents or []
    present_types = {d.document_type for d in documents if d.document_type}
    missing = [m for m in required if m.document_type not in present_types]

    return ExpertReport(
        packet_id=packet_id,
        pack=pack,
        verdict=verdict,
        readiness_score=score,
        executive_summary=_executive_summary(
            pack, verdict, score, findings, missing, len(documents)
        ),
        documents_detected=documents,
        missing_documents=missing,
        extracted_fields=extracted,
        findings=findings,
        recommended_actions=_recommended_actions(findings),
        redaction_summary=redaction_summary or RedactionSummary(),
        export_summary=export_summary or ExportSummary(),
        audit_summary=AuditSummary(),
        model_versions=model_versions or {},
        generated_at=datetime.now(tz=UTC).isoformat(),
    )
