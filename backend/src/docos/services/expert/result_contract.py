"""Unified ResultContract — one response shape for Clean Before Send and packet audit."""

from __future__ import annotations

from docos.services.expert.schemas import ExpertFinding, ExpertReport, ResultContract
from docos.services.expert.scoring import readiness_score, verdict_from
from docos.services.provenance.readiness import ReadinessReport

_READINESS_VERDICT = {
    "ready": "ready",
    "needs_fixes": "needs_review",
    "blocked": "blocked",
}


def from_readiness(
    doc_id: str,
    report: ReadinessReport,
    findings: list[ExpertFinding],
) -> ResultContract:
    """Compose a ResultContract from a single-document readiness report."""
    expert_verdict = verdict_from(findings)
    if report.verdict == "blocked":
        expert_verdict = "blocked"
    score = int(readiness_score(findings) * 100)
    fix_plans = sum(1 for f in findings if f.fix_available)
    human = any(f.human_review_required for f in findings) or any(
        c.status == "warn" and not c.fixable for c in report.checks
    )
    return ResultContract(
        job_type="clean_before_send",
        verdict=_READINESS_VERDICT.get(report.verdict, expert_verdict),
        score=score,
        findings=findings,
        fix_plans_available=fix_plans,
        clean_export_available=report.verdict != "blocked",
        proof_report_url=f"/documents/{doc_id}/readiness/report?format=html",
        human_review_required=human,
    )


def from_expert_report(packet_id: str, report: ExpertReport) -> ResultContract:
    """Compose a ResultContract from a packet ExpertReport."""
    fix_plans = sum(1 for f in report.findings if f.fix_available)
    return ResultContract(
        job_type="packet_audit",
        verdict=report.verdict,
        score=int(report.readiness_score * 100),
        findings=report.findings,
        fix_plans_available=fix_plans,
        clean_export_available=report.verdict != "blocked",
        proof_report_url=f"/packets/{packet_id}/report/download?format=html",
        human_review_required=any(f.human_review_required for f in report.findings),
    )
