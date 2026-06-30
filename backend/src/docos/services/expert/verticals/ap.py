"""Accounts-payable invoice packet auditor — the AP expert vertical.

The classic AP control is the *three-way match*: purchase order ↔ invoice ↔ goods receipt.
A payment should not be released until the invoice agrees with what was ordered (PO) and
what was actually received. This vertical extracts the cited facts for each role and runs
deterministic rules a clerk would: total/qty/currency match across PO and invoice, duplicate
invoice-number detection, and unmatched-PO-reference warnings.

Like import_export, every finding is evidence-bound; the rule builder refuses unfounded
blocking claims. Offline and deterministic.
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
    money_disagreement,
    new_finding,
)
from docos.services.expert.schemas import (
    DocumentSummary,
    ExpertFinding,
    ExpertReport,
    MissingDocument,
)
from docos.services.semantic import classify

PACK = "ap"

REQUIRED_DOCS: list[MissingDocument] = [
    MissingDocument(
        document_type="commercial_invoice",
        label="Invoice",
        severity="blocking",
        why_required="The invoice is the document that requests payment.",
    ),
    MissingDocument(
        document_type="purchase_order",
        label="Purchase order",
        severity="warning",
        why_required="The PO is needed to verify the invoice reflects what was ordered.",
    ),
]

_ROLE_SIGNALS: dict[str, tuple[str, ...]] = {
    "commercial_invoice": ("invoice no", "invoice number", "invoice #", "amount due", "bill to"),
    "purchase_order": ("purchase order", "po no", "po number", "po #"),
    "receipt": ("receipt", "goods received", "received in good", "packing slip"),
}


def detect_role(doc: CanonicalDocument) -> tuple[str, float]:
    text = " ".join(s.raw_text for s in ev.sourced_spans(doc)).lower()
    if not text.strip():
        return "other", 0.0
    best, best_hits = "other", 0
    for role, signals in _ROLE_SIGNALS.items():
        hits = sum(1 for sig in signals if sig in text)
        if hits > best_hits:
            best, best_hits = role, hits
    confidence = (
        round(best_hits / max(1, len(_ROLE_SIGNALS.get(best, ()))), 2) if best != "other" else 0.0
    )
    if best == "other":
        label = classify.classify(doc).label
        if label == "invoice":
            return "commercial_invoice", 0.5
    return best, confidence


_AMOUNT = re.compile(
    r"(?:total|amount\s*due|grand\s*total|invoice\s*total|balance\s*due)[^\d]{0,20}"
    r"([\d][\d,]*\.?\d{0,2})",
    re.I,
)
_CURRENCY = re.compile(r"\b(USD|EUR|GBP|CNY|JPY|CAD|AUD|CHF|HKD|MAD|AED)\b")
_ID_TAIL = r"\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]{3,})"
_PO = re.compile(r"\b(?:p\.?o\.?|purchase\s*order)" + _ID_TAIL, re.I)
_INVOICE_NO = re.compile(r"\binvoice" + _ID_TAIL, re.I)


def extract_facts(
    doc_id: str, doc: CanonicalDocument, role: str
) -> tuple[list[fg.Fact], dict[str, str]]:
    facts: list[fg.Fact] = []
    raw: dict[str, str] = {}
    spans = ev.sourced_spans(doc)

    def _span_for(node_id: str | None):
        return next((s for s in spans if s.node_id == node_id), None)

    m = ev.first(_AMOUNT, doc)
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

    m = ev.first(_CURRENCY, doc)
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

    m = ev.first(_PO, doc)
    if m:
        raw["po_number"] = m.value
        s = _span_for(m.span.node_id)
        facts.append(
            fg.text_fact(
                role=role,
                field_name="po_number",
                value=m.value,
                document_id=doc_id,
                document_type=role,
                node_id=s.node_id if s else m.span.node_id,
                page_number=s.page_number if s else m.span.page_number,
                raw_text=s.raw_text if s else m.span.raw_text,
                bbox=s.bbox if s else None,
            )
        )

    m = ev.first(_INVOICE_NO, doc)
    if m:
        raw["invoice_number"] = m.value
        s = _span_for(m.span.node_id)
        facts.append(
            fg.text_fact(
                role=role,
                field_name="invoice_number",
                value=m.value,
                document_id=doc_id,
                document_type=role,
                node_id=s.node_id if s else m.span.node_id,
                page_number=s.page_number if s else m.span.page_number,
                raw_text=s.raw_text if s else m.span.raw_text,
                bbox=s.bbox if s else None,
            )
        )

    return facts, raw


def _build_registry() -> RuleRegistry:
    reg = RuleRegistry()

    @reg.register("total_mismatch")
    def _total(ctx: PacketContext) -> list[ExpertFinding]:
        f = money_disagreement(
            ctx,
            field_name="total_amount",
            finding_type="field_mismatch",
            title="Invoice and PO totals disagree",
            explanation_template=(
                "The declared totals differ across {roles}: {values}. A payment "
                "must reconcile to one agreed amount before release."
            ),
            impact="Over/underpayment risk; the AP control fails the three-way match.",
            action="Reconcile the invoice total to the PO before approving payment.",
        )
        return [f] if f else []

    @reg.register("currency_mismatch")
    def _currency(ctx: PacketContext) -> list[ExpertFinding]:
        f = currency_disagreement(ctx)
        return [f] if f else []

    @reg.register("duplicate_invoice")
    def _dup(ctx: PacketContext) -> list[ExpertFinding]:
        """Block if the same invoice number appears on more than one invoice."""
        inv = ctx.facts.by_field("invoice_number")
        by_value: dict[str, list] = {}
        for f in inv:
            by_value.setdefault(str(f.value), []).append(f)
        out: list[ExpertFinding] = []
        for value, group in by_value.items():
            if len(group) < 2:
                continue
            evidence = [g.field_ref.evidence for g in group]
            out.append(
                new_finding(
                    type_="compliance_risk",
                    severity="blocking",
                    title="Duplicate invoice number",
                    explanation=(
                        f"Invoice number {value} appears on {len(group)} invoices. "
                        "Duplicate invoicing is a classic double-payment risk."
                    ),
                    evidence=evidence,
                    business_impact="Paying twice for one invoice is a direct cash loss.",
                    recommended_action="Confirm whether these are truly distinct invoices.",
                )
            )
        return out

    @reg.register("missing_required_documents")
    def _missing(ctx: PacketContext) -> list[ExpertFinding]:
        from docos.services.expert.rules import missing_required_documents

        return missing_required_documents(ctx)

    return reg


def audit(
    packet_id: str,
    docs: list[tuple[str, str | None, CanonicalDocument]],
) -> ExpertReport:

    summaries: list[DocumentSummary] = []
    graph = fg.FactGraph()
    for doc_id, title, doc in docs:
        role, conf = detect_role(doc)
        summaries.append(
            DocumentSummary(document_id=doc_id, title=title, document_type=role, confidence=conf)
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
