"""Rule registry — declarative contradiction / missing / compliance checks.

A rule is a pure function: ``PacketContext -> list[ExpertFinding]``. It reads normalized
facts from the fact graph and source docs from the packet, and returns only evidence-bound
findings. This keeps the comparison logic auditable and testable per-rule, and lets each
vertical register its own rules without touching the report assembler.

Design rule enforced here: a rule may NEVER invent evidence. If the signal it needs is
absent or ambiguous it must either (a) return nothing, or (b) return a finding with
``human_review_required=True`` and an explanation of why it cannot conclude. There is no
third option that fabricates a citation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from docos.services.expert.fact_graph import FactGraph
from docos.services.expert.schemas import (
    DocumentSummary,
    EvidenceRef,
    ExpertFinding,
    MissingDocument,
)

# A rule receives the fully-built packet context and yields zero or more findings.
Rule = Callable[["PacketContext"], list[ExpertFinding]]

# Severity helpers used by many rules.
_BLOCK = "blocking"
_WARN = "warning"
_INFO = "info"


@dataclass
class PacketContext:
    """Everything a rule needs to make a cited conclusion about one packet."""

    packet_id: str
    pack: str
    documents: list[DocumentSummary] = field(default_factory=list)
    facts: FactGraph = field(default_factory=FactGraph)
    # Per-document evidence refs that don't fit the typed fact model (e.g. raw PII spans).
    extra_evidence: dict[str, list[EvidenceRef]] = field(default_factory=dict)
    # Vertical-supplied: the required-document checklist (doc_type, label, why).
    required_documents: list[MissingDocument] = field(default_factory=list)


@dataclass
class RuleRegistry:
    """Per-pack registry of rules, run in registration order."""

    rules: list[tuple[str, Rule]] = field(default_factory=list)

    def register(self, code: str) -> Callable[[Rule], Rule]:
        def deco(fn: Rule) -> Rule:
            self.rules.append((code, fn))
            return fn

        return deco

    def run(self, ctx: PacketContext) -> list[ExpertFinding]:
        out: list[ExpertFinding] = []
        i = 0
        for _code, fn in self.rules:
            for finding in fn(ctx):
                if not finding.id:
                    finding = finding.model_copy(update={"id": f"{_code}-{i}"})
                if finding.rule_code is None:
                    finding = finding.model_copy(update={"rule_code": _code})
                out.append(finding)
                i += 1
        return out


def new_finding(
    *,
    type_: str,
    severity: str,
    title: str,
    explanation: str,
    evidence: list[EvidenceRef],
    business_impact: str | None = None,
    recommended_action: str | None = None,
    confidence: float = 1.0,
    human_review_required: bool = False,
    fix_available: bool = False,
) -> ExpertFinding:
    """Construct a finding, refusing to be created without evidence when severity>info."""
    if severity in (_BLOCK, _WARN) and not evidence and not human_review_required:
        # A blocking/warning claim with no evidence and no "needs human eyes" flag is a
        # hallucination. Force the author to either cite something or escalate to a human.
        raise ValueError(
            f"Refusing to build {severity} finding '{title}' with no evidence and no "
            "human_review_required. Cite a source or escalate — never assert unfounded."
        )
    return ExpertFinding(
        id="",  # assigned by the registry
        type=type_,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        title=title,
        explanation=explanation,
        business_impact=business_impact,
        recommended_action=recommended_action,
        evidence=evidence,
        confidence=confidence,
        detection_method="deterministic_rule",
        human_review_required=human_review_required,
        fix_available=fix_available,
    )


# ── Reusable cross-vertical comparison rules ───────────────────────────────────


def money_disagreement(
    ctx: PacketContext,
    *,
    field_name: str,
    finding_type: str,
    title: str,
    explanation_template: str,
    impact: str,
    action: str,
    tolerance_fraction: float = 0.01,
    tolerance_absolute: float = 0.01,
) -> ExpertFinding | None:
    """Generic "do the money values for ``field_name`` agree across roles?" rule."""
    facts = ctx.facts.by_field(field_name)
    money_facts = [f for f in facts if isinstance(f.value, (int, float))]
    if len(money_facts) < 2:
        return None
    values = [float(f.value) for f in money_facts]  # type: ignore[arg-type]
    spread = max(values) - min(values)
    threshold = max(tolerance_absolute, tolerance_fraction * max(values))
    if spread <= threshold:
        return None
    evidence: list[EvidenceRef] = [f.field_ref.evidence for f in money_facts]
    roles = ", ".join(sorted({f.role for f in money_facts}))
    return new_finding(
        type_=finding_type,
        severity=_BLOCK,
        title=title,
        explanation=explanation_template.format(
            roles=roles,
            values=", ".join(
                f"{f.unit or ''} {float(f.value):,.2f}".strip() for f in money_facts
            ),
            spread=spread,
        ),
        evidence=evidence,
        business_impact=impact,
        recommended_action=action,
    )


def currency_disagreement(ctx: PacketContext) -> ExpertFinding | None:
    """Block when documents declare different currency codes for the same money field."""
    seen: dict[str, list] = {}
    for f in ctx.facts.facts:
        if f.unit and f.unit not in seen:
            seen[f.unit] = []
        if f.unit:
            seen[f.unit].append(f)
    currencies = {c for c, fs in seen.items() if fs and c is not None}
    if len(currencies) <= 1:
        return None
    evidence: list[EvidenceRef] = []
    for fs in seen.values():
        evidence.extend(f.field_ref.evidence for f in fs)
    return new_finding(
        type_="currency_mismatch",
        severity=_BLOCK,
        title="Documents declare different currencies",
        explanation=(
            "The packet mixes currency codes "
            f"({', '.join(sorted(currencies))}); cross-currency totals cannot be compared "
            "directly and customs filings require a single declared currency."
        ),
        evidence=evidence,
        business_impact="Customs will reject or delay a packet with inconsistent currencies.",
        recommended_action="Standardize the packet to one currency before filing.",
    )


def weight_disagreement(
    ctx: PacketContext, *, field_name: str = "gross_weight"
) -> ExpertFinding | None:
    """Block when the same weight field disagrees across documents beyond tolerance."""
    facts = [f for f in ctx.facts.by_field(field_name) if isinstance(f.value, (int, float))]
    # Only compare within the same unit; mixed units need conversion (escalate, not assert).
    by_unit: dict[str | None, list] = {}
    for f in facts:
        by_unit.setdefault(f.unit, []).append(f)
    for unit, fs in by_unit.items():
        if len(fs) < 2:
            continue
        values = [float(f.value) for f in fs]  # type: ignore[arg-type]
        spread = max(values) - min(values)
        threshold = max(0.5, 0.01 * max(values))
        if spread <= threshold:
            continue
        evidence = [f.field_ref.evidence for f in fs]
        return new_finding(
            type_="weight_mismatch",
            severity=_BLOCK,
            title=f"{field_name} disagrees across documents",
            explanation=(
                f"{field_name} values differ by {spread:,.2f} {unit or 'kg'} across "
                f"{', '.join(sorted({f.role for f in fs}))}. Freight cost and customs "
                "duty both depend on weight; a mismatch will be queried."
            ),
            evidence=evidence,
            business_impact="Duty/freight may be recalculated; shipment can be held.",
            recommended_action="Reconcile the weight across the packing list and bill of lading.",
        )
    return None


def missing_required_documents(ctx: PacketContext) -> list[ExpertFinding]:
    """Flag every required document type that no packet document satisfied."""
    present_types = {d.document_type for d in ctx.documents if d.document_type}
    out: list[ExpertFinding] = []
    for req in ctx.required_documents:
        if req.document_type in present_types:
            continue
        out.append(
            new_finding(
                type_="missing_document",
                severity=req.severity,
                title=f"Missing {req.label}",
                explanation=(
                    f"No {req.label.lower()} was detected in the packet. {req.why_required}"
                ),
                evidence=[],  # absence has no positive citation
                business_impact="The packet is incomplete; a counterparty will request it.",
                recommended_action=f"Obtain and add a {req.label.lower()}.",
                # An absence cannot be cited, so it escalates to a human to confirm the doc
                # truly is missing (not merely mis-classified). Severity may still be warning.
                human_review_required=True,
            )
        )
    return out
