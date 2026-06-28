"""Finance / accounts-payable pack — deterministic invoice↔PO matching + duplicate detection.

The highest-ROI document vertical: every manually-processed invoice costs time, risks duplicate or
wrong payment, and delays close. This matches invoices to their purchase orders, compares totals and
currency, and flags duplicate invoice numbers — over the canonical model, offline, no LLM.

Reuses the shared shipment/finance field extractor from the import/export pack (invoice number, PO
number, total, currency), so the two packs stay consistent.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.packs.import_export import (
    PacketFinding,
    ShipmentFields,
    _visible_text,
    extract_shipment_fields,
)


class APMatch(BaseModel):
    invoice_doc_id: str
    po_number: str | None
    matched_po_doc_id: str | None
    total_matches: bool | None  # None when a total is missing on either side
    currency_matches: bool | None


class APReport(BaseModel):
    document_count: int
    documents: list[ShipmentFields]
    matches: list[APMatch]
    findings: list[PacketFinding]
    summary: str


def _role(f: ShipmentFields, text: str) -> str:
    """Decide invoice vs purchase_order from the visible text.

    The shared classifier labels both as ``invoice``, so it can't separate the two. The reliable
    signal is the document header / id fields: a purchase order says so and has no invoice number;
    an invoice carries an invoice number (or simply calls itself one).
    """
    low = text.lower()
    is_po_doc = f.doc_type == "purchase_order" or "purchase order" in low
    if is_po_doc and f.invoice_number is None:
        return "purchase_order"
    if f.invoice_number is not None or "invoice" in low:
        return "invoice"
    if f.po_number is not None:
        return "purchase_order"
    return "other"


def check_ap(docs: list[tuple[str, str | None, CanonicalDocument]]) -> APReport:
    """Match invoices to POs, compare totals/currency, and flag duplicate invoices."""
    fields = [extract_shipment_fields(did, title, doc) for did, title, doc in docs]
    roles = {
        f.doc_id: _role(f, _visible_text(doc)) for f, (_, _, doc) in zip(fields, docs, strict=True)
    }
    invoices = [f for f in fields if roles[f.doc_id] == "invoice"]
    pos = [f for f in fields if roles[f.doc_id] == "purchase_order"]
    po_by_number = {f.po_number: f for f in pos if f.po_number}

    findings: list[PacketFinding] = []

    # Duplicate invoice numbers — a classic double-payment risk.
    seen: dict[str, int] = {}
    for inv in invoices:
        if inv.invoice_number:
            seen[inv.invoice_number] = seen.get(inv.invoice_number, 0) + 1
    for number, count in seen.items():
        if count > 1:
            findings.append(
                PacketFinding(
                    severity="error",
                    code="duplicate_invoice",
                    message=f"Invoice number {number} appears {count} times — possible double pay.",
                )
            )

    matches: list[APMatch] = []
    for inv in invoices:
        po = po_by_number.get(inv.po_number) if inv.po_number else None
        total_ok: bool | None = None
        currency_ok: bool | None = None
        if po is not None:
            if inv.total is not None and po.total is not None:
                total_ok = abs(inv.total - po.total) <= max(0.01, 0.01 * max(inv.total, po.total))
                if not total_ok:
                    findings.append(
                        PacketFinding(
                            severity="error",
                            code="po_total_mismatch",
                            message=(
                                f"Invoice {inv.invoice_number or inv.doc_id} total {inv.total} "
                                f"≠ PO {inv.po_number} total {po.total}."
                            ),
                        )
                    )
            if inv.currency and po.currency:
                currency_ok = inv.currency == po.currency
                if not currency_ok:
                    findings.append(
                        PacketFinding(
                            severity="warn",
                            code="po_currency_mismatch",
                            message=f"Invoice {inv.invoice_number or inv.doc_id} currency "
                            f"{inv.currency} ≠ PO {po.currency}.",
                        )
                    )
        elif inv.po_number:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="po_not_found",
                    message=f"Invoice references PO {inv.po_number}, which is not in this set.",
                )
            )
        matches.append(
            APMatch(
                invoice_doc_id=inv.doc_id,
                po_number=inv.po_number,
                matched_po_doc_id=po.doc_id if po else None,
                total_matches=total_ok,
                currency_matches=currency_ok,
            )
        )

    errors = sum(1 for f in findings if f.severity == "error")
    matched = sum(1 for m in matches if m.matched_po_doc_id)
    if errors:
        summary = (
            f"{errors} blocking AP issue(s); "
            f"{matched}/{len(invoices)} invoice(s) matched to a PO."
        )
    else:
        summary = f"{matched}/{len(invoices)} invoice(s) matched to a PO; no blocking issues."
    return APReport(
        document_count=len(docs),
        documents=fields,
        matches=matches,
        findings=findings,
        summary=summary,
    )
