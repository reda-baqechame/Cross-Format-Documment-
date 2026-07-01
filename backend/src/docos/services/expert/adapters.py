"""Backward-compatible bridge from legacy pack reports to expert findings.

The five existing packs (import_export, finance, contracts, hr, insurance) each return
their own ``PacketReport`` with ``PacketFinding(severity/code/message)`` — no evidence.
Those endpoints keep working unchanged. This adapter lifts such a legacy report into the
expert vocabulary so the packet-audit API can surface every pack uniformly.

Legacy findings lack citations, so the adapter marks each ``human_review_required=True``
and ``detection_method="deterministic_rule"`` with ``confidence`` from the pack where
available, falling back to 1.0. This is honest: "we detected this rule but the legacy path
did not record which node — a human should confirm." The deep expert rebuilds (WS4) replace
these with fully-cited findings.
"""

from __future__ import annotations

from docos.services.expert.schemas import ExpertFinding

_LEGACY_SEVERITY = {"error": "blocking", "warn": "warning", "info": "info"}


def _map_type(code: str) -> str:
    code = (code or "").lower()
    table = {
        "currency_mismatch": "currency_mismatch",
        "total_mismatch": "field_mismatch",
        "po_total_mismatch": "field_mismatch",
        "weight_mismatch": "weight_mismatch",
        "origin_missing": "completeness_gap",
        "hs_code_missing": "hs_code_risk",
        "document_missing": "missing_document",
        "duplicate_invoice": "compliance_risk",
        "claim_outside_coverage": "compliance_risk",
    }
    return table.get(code, "other")


def legacy_finding_to_expert(
    finding,  # packs.*.PacketFinding
    *,
    idx: int,
    document_id: str | None = None,
) -> ExpertFinding:
    """Lift one legacy PacketFinding into an ExpertFinding (uncited → human review)."""
    severity = _LEGACY_SEVERITY.get(getattr(finding, "severity", "info"), "info")
    # Legacy findings have no evidence; blocking/warning would normally be refused by the
    # rule builder. Here we explicitly mark human_review_required so the absence is honest
    # rather than a silent unfounded claim.
    return ExpertFinding(
        id=f"legacy-{idx}",
        type=_map_type(getattr(finding, "code", "")),  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        title=getattr(finding, "code", "finding").replace("_", " ").title(),
        explanation=getattr(finding, "message", ""),
        evidence=[],
        confidence=1.0,
        detection_method="deterministic_rule",
        human_review_required=True,  # no citation recorded by the legacy path
        fix_available=False,
        rule_code=getattr(finding, "code", None),
    )
