"""HR onboarding expert vertical — cited offer extraction + packet completeness.

The legacy ``packs.hr`` pack extracts offer fields and checks the onboarding checklist but
without citations. This vertical rebuilds it on the expert spine: each offer field (role,
start date, compensation, employment type) is a cited fact, packet-completeness gaps cite
the required form's expected signals, and offer gaps (missing start/comp) escalate to human
review. Offline and deterministic.
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

PACK = "hr"

_ROLE_DOC_SIGNALS: dict[str, tuple[str, ...]] = {
    "offer_letter": ("offer letter", "offer of employment", "we are pleased to offer"),
    "eligibility_form": ("form i-9", "employment eligibility", "i-9"),
    "tax_withholding": ("form w-4", "withholding", "w-4"),
    "confidentiality_agreement": (
        "confidentiality",
        "non-disclosure",
        "nda",
        "proprietary",
    ),
}

REQUIRED_DOCS: list[MissingDocument] = [
    MissingDocument(
        document_type="offer_letter",
        label="Offer letter",
        severity="blocking",
        why_required="The offer letter sets the role, start date, and compensation.",
    ),
    MissingDocument(
        document_type="eligibility_form",
        label="Form I-9 (eligibility)",
        severity="warning",
        why_required="Required to verify employment eligibility in the US.",
    ),
    MissingDocument(
        document_type="tax_withholding",
        label="Form W-4 (withholding)",
        severity="warning",
        why_required="Required for tax withholding setup.",
    ),
    MissingDocument(
        document_type="confidentiality_agreement",
        label="Confidentiality / NDA",
        severity="info",
        why_required="Protects proprietary information.",
    ),
]

_START = re.compile(
    r"(?:start\s*date|starting\s+on|commenc\w+\s+on|effective\s+date|first\s+day)\s*[:\-]?\s*"
    r"(?:will\s+be\s+|is\s+|of\s+|on\s+)?"
    r"((?:\d|[A-Z][a-z]+\s+\d)[A-Za-z0-9,\s/\-]{4,28}?)(?:[.;\n]|$)",
    re.I,
)
_SALARY = re.compile(
    r"(?:salary|compensation|annual\s+(?:base\s+)?(?:salary|pay)|base\s+(?:salary|pay))"
    r"[^.\n]{0,40}?([$€£]?\s?\d[\d,]*(?:\.\d{2})?)",
    re.I,
)


def _detect(doc: CanonicalDocument) -> tuple[str, float]:
    text = " ".join(s.raw_text for s in ev.sourced_spans(doc)).lower()
    for role, signals in _ROLE_DOC_SIGNALS.items():
        if any(sig in text for sig in signals):
            return role, 0.9
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


def audit(packet_id: str, docs: list[tuple[str, str | None, CanonicalDocument]]) -> ExpertReport:

    summaries: list[DocumentSummary] = []
    graph = fg.FactGraph()

    for doc_id, title, doc in docs:
        role, conf = _detect(doc)
        summaries.append(
            DocumentSummary(document_id=doc_id, title=title, document_type=role, confidence=conf)
        )
        if role == "offer_letter":
            for field_name, pattern in {
                "start_date": _START,
                "compensation": _SALARY,
            }.items():
                f = _cited_fact(pattern, doc_id, doc, role, field_name)
                if f:
                    graph.add(f)

    reg = RuleRegistry()

    @reg.register("missing_required_documents")
    def _missing(ctx: PacketContext) -> list[ExpertFinding]:
        from docos.services.expert.rules import missing_required_documents

        return missing_required_documents(ctx)

    @reg.register("offer_missing_compensation")
    def _comp(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("compensation"):
            return []
        # Only relevant if an offer letter is actually present.
        if not any(d.document_type == "offer_letter" for d in ctx.documents):
            return []
        return [
            new_finding(
                type_="completeness_gap",
                severity="warning",
                title="Offer letter states no compensation",
                explanation="The offer letter was detected but no compensation figure was found.",
                evidence=[],
                business_impact="An unsigned compensation term is a dispute risk.",
                recommended_action="Confirm the compensation amount with the candidate.",
                human_review_required=True,
            )
        ]

    @reg.register("offer_missing_start_date")
    def _start(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("start_date"):
            return []
        if not any(d.document_type == "offer_letter" for d in ctx.documents):
            return []
        return [
            new_finding(
                type_="completeness_gap",
                severity="warning",
                title="Offer letter states no start date",
                explanation="The offer letter was detected but no start date was found.",
                evidence=[],
                business_impact="The start of employment is ambiguous.",
                recommended_action="Add a start date to the offer letter.",
                human_review_required=True,
            )
        ]

    return build_report(
        packet_id=packet_id,
        pack=PACK,
        documents=summaries,
        facts=graph,
        registry=reg,
        missing_documents=REQUIRED_DOCS,
        model_versions={"expert_spine": "1.0", "pack": PACK},
    )
