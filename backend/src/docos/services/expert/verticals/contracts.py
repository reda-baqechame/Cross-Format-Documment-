"""Contracts / CLM expert vertical — cited clause extraction + risk review.

The legacy ``packs.contracts`` pack extracts commercial terms but flags risks with no
citation (e.g. "no governing-law clause"). This vertical rebuilds it on the expert spine:
each clause is extracted as a cited fact, and each risk finding either cites the
problematic clause it found or — for an *absence* — explicitly escalates to human review
(an absence has no positive citation, so the rule builder only permits it with
``human_review_required``). This is the honest, auditor-grade contract first pass.
"""

from __future__ import annotations

import re

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
from docos.services.semantic import classify

PACK = "contracts"

_REQUIRED: list[MissingDocument] = [
    MissingDocument(
        document_type="contract",
        label="Contract / agreement",
        severity="blocking",
        why_required="A contract packet requires at least one agreement to review.",
    ),
]

_GOVERNING = re.compile(
    r"govern(?:ed|ing)?[^.]{0,40}?laws?\s+of\s+(?:the\s+)?(?:state\s+of\s+)?"
    r"(?:commonwealth\s+of\s+)?([A-Z][A-Za-z .]{2,30})",
    re.I,
)
_AUTO_RENEW = re.compile(
    r"automatically\s+renew|auto[\-\s]?renew|renew\s+automatically|"
    r"renewed?\s+for\s+(?:successive|additional)",
    re.I,
)
_TERMINATION = re.compile(
    r"terminat\w+[^.]{0,80}?(\d{1,3})\s*\)?\s*(?:calendar\s+|business\s+)?days",
    re.I,
)
_LIABILITY = re.compile(
    r"(?:liability[^.]{0,40}?(?:shall\s+not\s+exceed|limited\s+to|cap(?:pped)?)"
    r"|limit\w*\s+of\s+liability)",
    re.I,
)
_EFFECTIVE = re.compile(
    r"(?:effective\s*date|effective\s*as\s*of|dated)\s*[:\-]?\s*"
    r"([A-Za-z0-9,\s/\-]{6,30}?)(?:[.;\n]|$)",
    re.I,
)


def _detect(doc: CanonicalDocument) -> tuple[str, float]:
    label = classify.classify(doc).label
    if label in {"contract", "sow", "proposal"}:
        return "contract", 0.8
    text = " ".join(s.raw_text for s in ev.sourced_spans(doc)).lower()
    if any(k in text for k in ("agreement", "hereby", "the parties", "shall")):
        return "contract", 0.5
    return "other", 0.0


def _cited_text_fact(
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


def _cited_bool_fact(
    found: bool,
    match,
    doc_id: str,
    role: str,
    field_name: str,
) -> fg.Fact | None:
    """Build a cited fact for a boolean clause presence; cites the matched span when present."""
    if not found or match is None:
        return None
    raw_text = field_name
    node_id = None
    page = None
    bbox = None
    # match is an ev.Match from ev.first
    if hasattr(match, "span"):
        s = match.span
        node_id = s.node_id
        page = s.page_number
        raw_text = s.raw_text
        bbox = s.bbox
    return fg.text_fact(
        role=role,
        field_name=field_name,
        value="true",
        document_id=doc_id,
        document_type=role,
        node_id=node_id,
        page_number=page,
        raw_text=raw_text,
        bbox=bbox,
    )


def audit(packet_id: str, docs: list[tuple[str, str | None, CanonicalDocument]]) -> ExpertReport:

    summaries: list[DocumentSummary] = []
    graph = fg.FactGraph()

    for doc_id, title, doc in docs:
        role, conf = _detect(doc)
        summaries.append(
            DocumentSummary(document_id=doc_id, title=title, document_type=role, confidence=conf)
        )
        for field_name, pattern in {
            "governing_law": _GOVERNING,
            "termination_notice_days": _TERMINATION,
            "effective_date": _EFFECTIVE,
        }.items():
            f = _cited_text_fact(pattern, doc_id, doc, role, field_name)
            if f:
                graph.add(f)
        # Boolean clause presence (cited when present).
        m_liab = ev.first(_LIABILITY, doc)
        if m_liab:
            graph.add(
                _cited_bool_fact(True, m_liab, doc_id, role, "has_liability_cap")  # type: ignore[arg-type]
            )
        m_renew = ev.first(_AUTO_RENEW, doc)
        if m_renew:
            graph.add(
                _cited_bool_fact(True, m_renew, doc_id, role, "auto_renew")  # type: ignore[arg-type]
            )

    reg = RuleRegistry()

    @reg.register("governing_law_missing")
    def _gov(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("governing_law"):
            return []
        return [
            new_finding(
                type_="compliance_risk",
                severity="warning",
                title="No governing-law clause found",
                explanation="No clause specifies the jurisdiction whose laws govern the contract.",
                evidence=[],
                business_impact=(
                    "Disputes have no agreed forum; litigation venue becomes contested."
                ),
                recommended_action="Add a governing-law clause naming the intended jurisdiction.",
                human_review_required=True,
            )
        ]

    @reg.register("liability_cap_missing")
    def _liab(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("has_liability_cap"):
            return []
        return [
            new_finding(
                type_="compliance_risk",
                severity="warning",
                title="No limitation-of-liability clause found",
                explanation="No cap on liability was detected.",
                evidence=[],
                business_impact="Exposure may be uncapped in the event of a breach.",
                recommended_action="Add a mutual limitation-of-liability clause.",
                human_review_required=True,
            )
        ]

    @reg.register("auto_renewal")
    def _renew(ctx: PacketContext) -> list[ExpertFinding]:
        facts = ctx.facts.by_field("auto_renew")
        if not facts:
            return []
        return [
            new_finding(
                type_="compliance_risk",
                severity="warning",
                title="Contract auto-renews",
                explanation="An auto-renewal clause was detected.",
                evidence=[f.field_ref.evidence for f in facts],
                business_impact=(
                    "The contract may lock in unless cancelled within its notice window."
                ),
                recommended_action=(
                    "Calendar the cancellation deadline and confirm the notice period."
                ),
            )
        ]

    @reg.register("termination_notice_missing")
    def _term(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("termination_notice_days"):
            return []
        return [
            new_finding(
                type_="completeness_gap",
                severity="warning",
                title="No termination notice period found",
                explanation="No termination-for-convenience notice period was detected.",
                evidence=[],
                business_impact="Exit terms are unclear; ending the contract may be contested.",
                recommended_action="Specify a termination notice period (e.g. 30 days).",
                human_review_required=True,
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
        missing_documents=_REQUIRED,
        model_versions={"expert_spine": "1.0", "pack": PACK},
        raw_docs=docs,
    )
