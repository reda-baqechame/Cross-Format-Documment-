"""Invoice skill — the flagship deep skill (the #1-demand document type).

Extracts the fields that matter for an invoice, then runs the checks a human would: do the
numbers add up, is there a due date and an invoice number, is there exposed PII. Recommends the
actions an AP clerk actually takes next (export to Excel, redact, seal).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import (
    DocumentSkill,
    ExtractedField,
    FieldFinder,
    RecommendedAction,
    SkillFinding,
    money_to_float,
)
from docos.services.semantic.skills.generic import pii_warning

_SYNONYMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("supplier", "Supplier"): ("supplier", "vendor", "sold by", "bill from", "from"),
    ("invoice_number", "Invoice #"): ("invoice number", "invoice no", "invoice #", "inv no"),
    ("invoice_date", "Invoice date"): ("invoice date", "date of issue", "issued", "date"),
    ("due_date", "Due date"): ("due date", "payment due", "due"),
    ("subtotal", "Subtotal"): ("subtotal", "sub total", "sub-total"),
    ("tax", "Tax"): ("tax", "vat", "gst", "sales tax"),
    ("total", "Total"): ("total due", "amount due", "balance due", "grand total", "total"),
}


class InvoiceSkill(DocumentSkill):
    label = "invoice"
    title = "Invoice"
    category = "financial"
    required_fields = {"total", "invoice_number"}

    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]:
        finder = FieldFinder(doc)
        fields = [finder.field(name, label, syns) for (name, label), syns in _SYNONYMS.items()]
        by_name = {f.name: f for f in fields}

        # Entity fallbacks for the two most important fields: total = largest money amount.
        if by_name["total"].status == "missing":
            money_pairs = [(money_to_float(v), v, nid) for v, nid in finder.entities("money")]
            money_pairs = [(amt, v, nid) for amt, v, nid in money_pairs if amt is not None]
            if money_pairs:
                _amt, value, node_id = max(money_pairs, key=lambda t: t[0])
                by_name["total"] = ExtractedField(
                    name="total",
                    label="Total",
                    value=value,
                    confidence=0.5,
                    node_id=node_id,
                    status="low_confidence",
                )
        if by_name["invoice_date"].status == "missing":
            dates = finder.entities("date")
            if dates:
                value, node_id = dates[0]
                by_name["invoice_date"] = ExtractedField(
                    name="invoice_date",
                    label="Invoice date",
                    value=value,
                    confidence=0.5,
                    node_id=node_id,
                    status="low_confidence",
                )
        return list(by_name.values())

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        findings: list[SkillFinding] = []
        by_name = {f.name: f for f in fields}

        subtotal = money_to_float(by_name["subtotal"].value)
        tax = money_to_float(by_name["tax"].value)
        total = money_to_float(by_name["total"].value)
        if subtotal is not None and tax is not None and total is not None:
            if abs((subtotal + tax) - total) > 0.01:
                findings.append(
                    SkillFinding(
                        level="fail",
                        code="totals.mismatch",
                        message=(
                            f"Subtotal + tax ({subtotal + tax:.2f}) does not equal "
                            f"the stated total ({total:.2f})."
                        ),
                    )
                )
            else:
                findings.append(
                    SkillFinding(
                        level="pass",
                        code="totals.match",
                        message="Subtotal + tax equals the stated total.",
                    )
                )

        if by_name["invoice_number"].status == "missing":
            findings.append(
                SkillFinding(
                    level="warn", code="missing.invoice_number", message="No invoice number found."
                )
            )
        if by_name["due_date"].status == "missing":
            findings.append(
                SkillFinding(
                    level="warn", code="missing.due_date", message="No payment due date found."
                )
            )
        warning = pii_warning(doc)
        if warning:
            findings.append(warning)
        return findings

    def recommend(
        self,
        doc: CanonicalDocument,
        fields: list[ExtractedField],
        findings: list[SkillFinding],
    ) -> list[RecommendedAction]:
        actions = [
            RecommendedAction(
                id="export_xlsx",
                label="Export to Excel",
                kind="export",
                params={"format": "xlsx"},
            )
        ]
        if any(f.code == "pii.present" for f in findings):
            actions.append(
                RecommendedAction(id="redact", label="Redact personal info", kind="redact")
            )
        actions.append(RecommendedAction(id="seal", label="Add integrity seal", kind="sign"))
        return actions
