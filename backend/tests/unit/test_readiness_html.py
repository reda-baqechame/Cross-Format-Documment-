"""HTML readiness report rendering."""

from __future__ import annotations

from docos.services.provenance.readiness import ReadinessCheck, ReadinessReport
from docos.services.provenance.readiness_html import render_readiness_html


def test_render_includes_checks_and_actions():
    report = ReadinessReport(
        verdict="needs_fixes",
        summary="2 issue(s) to review before sending.",
        checks=[
            ReadinessCheck(
                id="payment_terms",
                label="Payment terms",
                status="warn",
                detail="No deposit or net terms found.",
            ),
            ReadinessCheck(
                id="exposed_pii",
                label="Sensitive data",
                status="fail",
                detail="1 email address exposed.",
                fixable=True,
                fix_action="redact_pii",
            ),
        ],
    )
    html = render_readiness_html(title="Acme Proposal", doc_id="doc_test", report=report)
    assert "Payment terms" in html
    assert "Recommended next steps" in html
    assert "Run in DocOS" in html
    assert "doc_test" in html


def test_render_includes_expert_findings():
    from docos.services.expert.rules import new_finding

    report = ReadinessReport(
        verdict="needs_fixes",
        summary="1 issue.",
        checks=[
            ReadinessCheck(
                id="exposed_pii",
                label="Sensitive data",
                status="warn",
                detail="1 email exposed.",
            )
        ],
    )
    findings = [
        new_finding(
            type_="redaction_risk",
            severity="warning",
            title="Sensitive data exposed",
            explanation="Email found in body.",
            evidence=[],
            human_review_required=True,
        )
    ]
    html = render_readiness_html(
        title="Acme", doc_id="doc_x", report=report, expert_findings=findings
    )
    assert "Expert findings" in html
    assert "Sensitive data exposed" in html
