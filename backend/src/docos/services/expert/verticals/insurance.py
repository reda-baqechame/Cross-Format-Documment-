"""Insurance policy/claims expert vertical — cited declarations + coverage checks.

The legacy ``packs.insurance`` pack extracts policy/claim fields and checks expiry/coverage
without citations. This vertical rebuilds it on the expert spine: each declaration (policy
number, claim number, coverage limit, premium, deductible, effective/expiration/loss dates)
is a cited fact, and the coverage/expiry/claim-within-period rules cite the spans they read.
A claim filed outside the coverage period is blocking and cites both the loss date and the
policy window. Offline and deterministic.
"""

from __future__ import annotations

import re
from datetime import datetime

from docos.model.document import CanonicalDocument
from docos.services.expert import evidence as ev
from docos.services.expert import fact_graph as fg
from docos.services.expert.report import build_report
from docos.services.expert.rules import (
    PacketContext,
    RuleRegistry,
    new_finding,
)
from docos.services.expert.schemas import (
    DocumentSummary,
    ExpertFinding,
    ExpertReport,
    MissingDocument,
)

PACK = "insurance"

REQUIRED_DOCS: list[MissingDocument] = [
    MissingDocument(
        document_type="policy",
        label="Insurance policy / declarations",
        severity="blocking",
        why_required="The policy declarations define the coverage that applies.",
    ),
]

_MONEY = r"([$€£]?\s?\d[\d,]*(?:\.\d{2})?)"
_COVERAGE = re.compile(
    r"(?:coverage\s*limit|limit\s*of\s*liability|sum\s*insured|coverage\s*amount)"
    r"[^.\n]{0,40}?" + _MONEY,
    re.I,
)
_DEDUCTIBLE = re.compile(r"(?:deductible|excess)[^.\n]{0,40}?" + _MONEY, re.I)
_EFFECTIVE = re.compile(
    r"(?:effective\s*date|policy\s*period\s*from|inception)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)
_EXPIRATION = re.compile(
    r"(?:expiration\s*date|expiry|expires?|policy\s*period\s*to|valid\s*(?:un)?til)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)
_CLAIM_DATE = re.compile(
    r"(?:date\s*of\s*loss|loss\s*date|date\s*of\s*claim|incident\s*date)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)


def _detect(doc: CanonicalDocument) -> tuple[str, float]:
    text = " ".join(s.raw_text for s in ev.sourced_spans(doc)).lower()
    if any(k in text for k in ("policy", "coverage", "premium", "deductible")):
        if any(k in text for k in ("claim", "date of loss", "incident")):
            return "claim", 0.8
        return "policy", 0.7
    return "other", 0.0


def _cited_fact(
    pattern: re.Pattern[str],
    doc_id: str,
    doc: CanonicalDocument,
    role: str,
    field_name: str,
) -> fg.Fact | None:
    m = ev.first(pattern, doc)
    if not m:
        return None
    spans = ev.sourced_spans(doc)
    s = next((sp for sp in spans if sp.node_id == m.span.node_id), None)
    return fg.text_fact(
        role=role,
        field_name=field_name,
        value=m.value.strip(" .,;:"),
        document_id=doc_id,
        document_type=role,
        node_id=s.node_id if s else m.span.node_id,
        page_number=s.page_number if s else m.span.page_number,
        raw_text=s.raw_text if s else m.span.raw_text,
        bbox=s.bbox if s else None,
    )


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def audit(packet_id: str, docs: list[tuple[str, str | None, CanonicalDocument]]) -> ExpertReport:

    summaries: list[DocumentSummary] = []
    graph = fg.FactGraph()

    for doc_id, title, doc in docs:
        role, conf = _detect(doc)
        summaries.append(
            DocumentSummary(document_id=doc_id, title=title, document_type=role, confidence=conf)
        )
        for field_name, pattern in {
            "coverage_limit": _COVERAGE,
            "deductible": _DEDUCTIBLE,
            "effective_date": _EFFECTIVE,
            "expiration_date": _EXPIRATION,
            "loss_date": _CLAIM_DATE,
        }.items():
            f = _cited_fact(pattern, doc_id, doc, role, field_name)
            if f:
                graph.add(f)

    reg = RuleRegistry()

    @reg.register("missing_coverage_limit")
    def _cov(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("coverage_limit"):
            return []
        return [
            new_finding(
                type_="completeness_gap",
                severity="warning",
                title="No coverage limit stated",
                explanation="No coverage limit / sum insured was found on the policy.",
                evidence=[],
                business_impact="The exposure covered by the policy is unknown.",
                recommended_action="State the coverage limit on the declarations page.",
                human_review_required=True,
            )
        ]

    @reg.register("expired_policy")
    def _exp(ctx: PacketContext) -> list[ExpertFinding]:
        exp_facts = ctx.facts.by_field("expiration_date")
        out: list[ExpertFinding] = []
        for f in exp_facts:
            d = _parse_date(str(f.value))
            if d and d < datetime.now():
                out.append(
                    new_finding(
                        type_="compliance_risk",
                        severity="blocking",
                        title="Policy is expired",
                        explanation=(f"The policy expiration date {f.value} is in the past."),
                        evidence=[f.field_ref.evidence],
                        business_impact="A claim against an expired policy is not covered.",
                        recommended_action="Renew the policy or confirm active coverage.",
                    )
                )
        return out

    @reg.register("claim_outside_coverage")
    def _claim(ctx: PacketContext) -> list[ExpertFinding]:
        loss = ctx.facts.by_field("loss_date")
        eff = ctx.facts.one("policy", "effective_date") or ctx.facts.by_field("effective_date")
        exp = ctx.facts.one("policy", "expiration_date") or ctx.facts.by_field("expiration_date")
        eff_list = eff if isinstance(eff, list) else [eff] if eff else []
        exp_list = exp if isinstance(exp, list) else [exp] if exp else []
        if not loss or not eff_list or not exp_list:
            return []
        loss_d = _parse_date(str(loss[0].value))
        eff_d = _parse_date(str(eff_list[0].value))
        exp_d = _parse_date(str(exp_list[0].value))
        if not (loss_d and eff_d and exp_d):
            return []
        if eff_d <= loss_d <= exp_d:
            return []
        return [
            new_finding(
                type_="compliance_risk",
                severity="blocking",
                title="Claim falls outside the coverage period",
                explanation=(
                    f"The loss date {loss[0].value} is outside the policy period "
                    f"({eff_list[0].value} – {exp_list[0].value})."
                ),
                evidence=[
                    loss[0].field_ref.evidence,
                    eff_list[0].field_ref.evidence,
                    exp_list[0].field_ref.evidence,
                ],
                business_impact="A claim outside the coverage period will be denied.",
                recommended_action=(
                    "Confirm whether an endorsement extends coverage to the loss date."
                ),
            )
        ]

    @reg.register("missing_required_documents")
    def _missing(ctx: PacketContext) -> list[ExpertFinding]:
        from docos.services.expert.rules import missing_required_documents

        return missing_required_documents(ctx)

    return build_report(
        packet_id=packet_id,
        pack=PACK,
        documents=summaries,
        facts=graph,
        registry=reg,
        missing_documents=REQUIRED_DOCS,
        model_versions={"expert_spine": "1.0", "pack": PACK},
    )
