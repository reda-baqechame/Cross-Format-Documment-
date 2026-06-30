"""Readiness scoring + verdict derivation.

The verdict and readiness score are deterministic functions of the findings, never a
model's opinion. This is what makes the report auditable and what the UI's "BLOCKED /
NEEDS REVIEW / READY" badge trusts.
"""

from __future__ import annotations

from docos.services.expert.schemas import ExpertFinding, Verdict

_SEVERITY_WEIGHT = {"blocking": 1.0, "warning": 0.25, "info": 0.0}
# A score of 1.0 = ready; each blocking finding drops to 0; warnings shave points.
# This is intentionally simple and explainable, not a learned model.


def verdict_from(findings: list[ExpertFinding]) -> Verdict:
    has_blocking = any(f.severity == "blocking" for f in findings)
    has_warning = any(f.severity == "warning" for f in findings)
    needs_human = any(f.human_review_required for f in findings)
    if has_blocking:
        return "blocked"
    if has_warning or needs_human:
        return "needs_review"
    return "ready"


def readiness_score(findings: list[ExpertFinding]) -> float:
    """1.0 minus the capped sum of finding penalties, clamped to [0, 1]."""
    if not findings:
        return 1.0
    penalty = sum(_SEVERITY_WEIGHT.get(f.severity, 0.0) * f.confidence for f in findings)
    return max(0.0, 1.0 - penalty)
