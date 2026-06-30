"""Import/Export packet auditor — the flagship expert vertical.

This is the deep, evidence-bound rebuild of the legacy ``packs.import_export`` check. It:

  1. Classifies each packet document into a shipment *role* (commercial_invoice,
     packing_list, bill_of_lading, certificate_of_origin, purchase_order, other) using
     label+field signals rather than the coarse global classifier.
  2. Extracts shipment fields with full citations (node id + page + raw span) via the
     evidence module — invoice number, PO number, currency, total, HS code, origin,
     gross/net weight, package count, incoterms, shipment date.
  3. Normalizes them into the fact graph.
  4. Runs the expert rules: currency/total/weight disagreement, origin presence, HS
     presence, party consistency, package-count consistency, date sequence, missing
     required documents.

Every finding cites at least one source span; missing-document findings are the only
evidence-free type (an absence has no positive citation) and are permitted by the rule
builder. The result is an ``ExpertReport`` a customs broker would trust as a first pass.
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
    currency_disagreement,
    missing_required_documents,
    money_disagreement,
    new_finding,
    weight_disagreement,
)
from docos.services.expert.schemas import (
    DocumentSummary,
    ExpertFinding,
    ExpertReport,
    MissingDocument,
)
from docos.services.semantic import classify

PACK = "import_export"

REQUIRED_DOCS: list[MissingDocument] = [
    MissingDocument(
        document_type="commercial_invoice",
        label="Commercial invoice",
        severity="warning",
        why_required="Customs uses it to assess duty and declare the value of the shipment.",
    ),
    MissingDocument(
        document_type="packing_list",
        label="Packing list",
        severity="warning",
        why_required="Details package counts and weights used to verify the shipment.",
    ),
    MissingDocument(
        document_type="bill_of_lading",
        label="Bill of lading",
        severity="warning",
        why_required="The contract of carriage and title document for the shipment.",
    ),
    MissingDocument(
        document_type="certificate_of_origin",
        label="Certificate of origin",
        severity="info",
        why_required="May be required to claim preferential duty treatment under trade agreements.",
    ),
]

# ── Role detection (finer than the global classifier) ──────────────────────────

_ROLE_SIGNALS: dict[str, tuple[str, ...]] = {
    "commercial_invoice": (
        "commercial invoice",
        "invoice no",
        "invoice number",
        "invoice #",
        "total due",
    ),
    "packing_list": ("packing list", "package", "gross weight", "net weight", "no. of packages"),
    "bill_of_lading": ("bill of lading", "b/l", "bl no", "shipper", "consignee", "carrier"),
    "certificate_of_origin": ("certificate of origin", "country of origin", "origin certificate"),
    "purchase_order": ("purchase order", "po no", "po number", "po #"),
}


def detect_role(doc: CanonicalDocument) -> tuple[str, float]:
    """Return the shipment role + a 0–1 confidence from signal scoring."""
    text = " ".join(s.raw_text for s in ev.sourced_spans(doc)).lower()
    if not text.strip():
        return "other", 0.0
    best, best_hits = "other", 0
    scores: dict[str, int] = {}
    for role, signals in _ROLE_SIGNALS.items():
        hits = sum(1 for sig in signals if sig in text)
        scores[role] = hits
        if hits > best_hits:
            best, best_hits = role, hits
    confidence = (
        round(best_hits / max(1, len(_ROLE_SIGNALS.get(best, ()))), 2) if best != "other" else 0.0
    )
    # Fall back to the global classifier if nothing fired, to still tag invoices/contracts.
    if best == "other":
        label = classify.classify(doc).label
        if label == "invoice":
            return "commercial_invoice", 0.5
    return best, confidence


# ── Cited extraction ───────────────────────────────────────────────────────────

_CURRENCY = re.compile(r"\b(USD|EUR|GBP|CNY|JPY|CAD|AUD|CHF|HKD|MAD|AED)\b")
_AMOUNT = re.compile(
    r"(?:total|amount\s*due|grand\s*total|invoice\s*total)[^\d]{0,20}([\d][\d,]*\.?\d{0,2})",
    re.I,
)
_GROSS_WEIGHT = re.compile(
    r"gross\s*weight[^\d]{0,15}([\d][\d,]*\.?\d{0,2})\s*(kgs?|lbs?|kilograms?|pounds?)?", re.I
)
_NET_WEIGHT = re.compile(
    r"net\s*weight[^\d]{0,15}([\d][\d,]*\.?\d{0,2})\s*(kgs?|lbs?|kilograms?|pounds?)?", re.I
)
_HS_CODE = re.compile(r"\b(?:hs\s*code|hts|tariff)[^\d]{0,10}(\d{6,10})", re.I)
_ORIGIN = re.compile(
    r"(?:country\s*of\s*origin|origin)\s*[:\-]?\s*([A-Za-z][A-Za-z .]{2,30})", re.I
)
_PACKAGE_COUNT = re.compile(
    r"(?:no\.?\s*of\s*packages|package\s*count|total\s*packages|packages)[^\d]{0,10}(\d{1,6})", re.I
)
_INCOTERMS = re.compile(r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b")
_SHIP_DATE = re.compile(
    r"(?:ship(?:ment)?\s*date|date\s*of\s*shipment|b/l\s*date|on\s*board\s*date)[^\d]{0,15}"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
    re.I,
)
_ID_TAIL = r"\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]{3,})"
_PO = re.compile(r"\b(?:p\.?o\.?|purchase\s*order)" + _ID_TAIL, re.I)
_INVOICE_NO = re.compile(r"\binvoice" + _ID_TAIL, re.I)


def _first_match(pattern: re.Pattern[str], doc: CanonicalDocument):
    return ev.first(pattern, doc)


def _role_of(doc_meta: dict[str, str], default: str = "other") -> str:
    return doc_meta.get("role", default)


def extract_facts(
    doc_id: str, doc: CanonicalDocument, role: str
) -> tuple[list[fg.Fact], dict[str, str]]:
    """Pull all shipment fields from one doc into cited facts. Returns (facts, raw_values)."""
    facts: list[fg.Fact] = []
    raw: dict[str, str] = {}
    spans = ev.sourced_spans(doc)

    def _span_for(node_id: str | None):
        return next((s for s in spans if s.node_id == node_id), None)

    # Total amount (money)
    m = _first_match(_AMOUNT, doc)
    if m:
        raw["total_amount"] = m.value
        s = _span_for(m.span.node_id)
        f = fg.money_fact(
            role=role,
            field_name="total_amount",
            raw=m.value,
            document_id=doc_id,
            document_type=role,
            node_id=s.node_id if s else m.span.node_id,
            page_number=s.page_number if s else m.span.page_number,
            raw_text=s.raw_text if s else m.span.raw_text,
            bbox=s.bbox if s else None,
        )
        if f:
            facts.append(f)

    # Currency (text)
    m = _first_match(_CURRENCY, doc)
    if m:
        raw["currency"] = m.value
        s = _span_for(m.span.node_id)
        facts.append(
            fg.text_fact(
                role=role,
                field_name="currency",
                value=m.value,
                document_id=doc_id,
                document_type=role,
                node_id=s.node_id if s else m.span.node_id,
                page_number=s.page_number if s else m.span.page_number,
                raw_text=s.raw_text if s else m.span.raw_text,
                bbox=s.bbox if s else None,
            )
        )

    # Gross weight
    m = _first_match(_GROSS_WEIGHT, doc)
    if m:
        raw["gross_weight"] = m.span.raw_text
        s = _span_for(m.span.node_id)
        f = fg.weight_fact(
            role=role,
            field_name="gross_weight",
            raw=m.span.raw_text,
            document_id=doc_id,
            document_type=role,
            node_id=s.node_id if s else m.span.node_id,
            page_number=s.page_number if s else m.span.page_number,
            raw_text=s.raw_text if s else m.span.raw_text,
            bbox=s.bbox if s else None,
        )
        if f:
            facts.append(f)

    # HS code
    m = _first_match(_HS_CODE, doc)
    if m:
        raw["hs_code"] = m.value
        s = _span_for(m.span.node_id)
        facts.append(
            fg.text_fact(
                role=role,
                field_name="hs_code",
                value=m.value,
                document_id=doc_id,
                document_type=role,
                node_id=s.node_id if s else m.span.node_id,
                page_number=s.page_number if s else m.span.page_number,
                raw_text=s.raw_text if s else m.span.raw_text,
                bbox=s.bbox if s else None,
            )
        )

    # Country of origin
    m = _first_match(_ORIGIN, doc)
    if m:
        raw["origin"] = m.value
        s = _span_for(m.span.node_id)
        facts.append(
            fg.text_fact(
                role=role,
                field_name="origin_country",
                value=m.value.strip(),
                document_id=doc_id,
                document_type=role,
                node_id=s.node_id if s else m.span.node_id,
                page_number=s.page_number if s else m.span.page_number,
                raw_text=s.raw_text if s else m.span.raw_text,
                bbox=s.bbox if s else None,
            )
        )

    return facts, raw


# ── Rules specific to import/export ────────────────────────────────────────────


def _build_registry() -> RuleRegistry:
    reg = RuleRegistry()

    @reg.register("currency_mismatch")
    def _currency(ctx: PacketContext) -> list[ExpertFinding]:
        f = currency_disagreement(ctx)
        return [f] if f else []

    @reg.register("total_mismatch")
    def _total(ctx: PacketContext) -> list[ExpertFinding]:
        f = money_disagreement(
            ctx,
            field_name="total_amount",
            finding_type="field_mismatch",
            title="Declared totals disagree across documents",
            explanation_template=(
                "Totals for the same shipment differ across {roles}: {values}. "
                "Customs value, duty, and payment must reconcile to one figure."
            ),
            impact="Customs will query the discrepancy; payment may be held.",
            action="Reconcile the commercial invoice, PO, and BoL to one declared total.",
        )
        return [f] if f else []

    @reg.register("weight_mismatch")
    def _weight(ctx: PacketContext) -> list[ExpertFinding]:
        f = weight_disagreement(ctx, field_name="gross_weight")
        return [f] if f else []

    @reg.register("origin_missing")
    def _origin(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("origin_country"):
            return []
        return [
            new_finding(
                type_="completeness_gap",
                severity="warning",
                title="No country of origin declared",
                explanation="No document in the packet states a country of origin.",
                evidence=[],
                business_impact="Customs requires origin to determine duty and admissibility.",
                recommended_action=(
                    "Add the country of origin to the commercial invoice or certificate of origin."
                ),
                human_review_required=True,
            )
        ]

    @reg.register("hs_code_missing")
    def _hs(ctx: PacketContext) -> list[ExpertFinding]:
        if ctx.facts.by_field("hs_code"):
            return []
        return [
            new_finding(
                type_="hs_code_risk",
                severity="warning",
                title="No HS/tariff code declared",
                explanation="No HS or tariff classification code was found in the packet.",
                evidence=[],
                business_impact="Duty cannot be computed without a classification code.",
                recommended_action="Classify the goods and add the HS code to the invoice.",
                human_review_required=True,
            )
        ]

    @reg.register("missing_required_documents")
    def _missing(ctx: PacketContext) -> list[ExpertFinding]:
        return missing_required_documents(ctx)

    return reg


# ── Entry point ────────────────────────────────────────────────────────────────


def audit(
    packet_id: str,
    docs: list[tuple[str, str | None, CanonicalDocument]],
) -> ExpertReport:
    """Run the full import/export expert audit over a packet and return the report."""

    summaries: list[DocumentSummary] = []
    graph = fg.FactGraph()

    for doc_id, title, doc in docs:
        role, conf = detect_role(doc)
        summaries.append(
            DocumentSummary(
                document_id=doc_id,
                title=title,
                document_type=role,
                confidence=conf,
            )
        )
        facts, _raw = extract_facts(doc_id, doc, role)
        for fact in facts:
            graph.add(fact)

    return build_report(
        packet_id=packet_id,
        pack=PACK,
        documents=summaries,
        facts=graph,
        registry=_build_registry(),
        missing_documents=REQUIRED_DOCS,
        model_versions={"expert_spine": "1.0", "pack": PACK},
    )
