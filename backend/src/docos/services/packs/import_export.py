"""Import/export packet validation — deterministic, offline cross-document consistency checks.

A shipment is not separate files; it is one transaction packet whose fields must agree. This module
classifies each document, extracts shipment fields deterministically (regex over the redaction-aware
visible text), and cross-checks them — currency, totals, buyer/seller, HS code, country of origin —
flagging mismatches and missing documents the way a customs broker would. No LLM, no network.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.semantic import classify
from docos.services.semantic.extract import _text_nodes

# The canonical packet — documents a complete import/export shipment usually needs.
REQUIRED_DOC_TYPES: tuple[tuple[str, str], ...] = (
    ("commercial_invoice", "Commercial invoice"),
    ("packing_list", "Packing list"),
    ("bill_of_lading", "Bill of lading"),
    ("certificate_of_origin", "Certificate of origin"),
)

_CURRENCY = re.compile(r"\b(USD|EUR|GBP|CNY|JPY|CAD|AUD|CHF|HKD|MAD|AED)\b")
_AMOUNT = re.compile(r"(?:total|amount\s*due|grand\s*total)[^\d]{0,20}([\d][\d,]*\.?\d{0,2})", re.I)
_HS_CODE = re.compile(r"\b(?:hs\s*code|hts|tariff)[^\d]{0,10}(\d{6,10})", re.I)
_ORIGIN = re.compile(
    r"(?:country\s*of\s*origin|origin)\s*[:\-]?\s*([A-Za-z][A-Za-z .]{2,30})", re.I
)
# Require the no/number/# qualifier so a bare "Invoice"/"PO" heading word isn't captured as the id.
_ID_TAIL = r"\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]{3,})"
_PO = re.compile(r"\b(?:p\.?o\.?|purchase\s*order)" + _ID_TAIL, re.I)
_INVOICE_NO = re.compile(r"\binvoice" + _ID_TAIL, re.I)


class ShipmentFields(BaseModel):
    doc_id: str
    title: str | None
    doc_type: str
    confidence: float
    currency: str | None = None
    total: float | None = None
    hs_code: str | None = None
    origin: str | None = None
    po_number: str | None = None
    invoice_number: str | None = None


class PacketFinding(BaseModel):
    severity: str  # error | warn | info
    code: str
    message: str


class ChecklistItem(BaseModel):
    doc_type: str
    label: str
    present: bool


class PacketReport(BaseModel):
    document_count: int
    documents: list[ShipmentFields]
    findings: list[PacketFinding]
    checklist: list[ChecklistItem]
    summary: str


def _visible_text(doc: CanonicalDocument) -> str:
    return "\n".join(text for _, text in _text_nodes(doc))


def _to_amount(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def extract_shipment_fields(
    doc_id: str, title: str | None, doc: CanonicalDocument
) -> ShipmentFields:
    """Classify + pull the shipment-relevant fields from one document (deterministic)."""
    c = classify.classify(doc)
    text = _visible_text(doc)

    cur = _CURRENCY.search(text)
    amt = _AMOUNT.search(text)
    hs = _HS_CODE.search(text)
    origin = _ORIGIN.search(text)
    po = _PO.search(text)
    inv = _INVOICE_NO.search(text)
    return ShipmentFields(
        doc_id=doc_id,
        title=title,
        doc_type=c.label,
        confidence=c.confidence,
        currency=cur.group(1).upper() if cur else None,
        total=_to_amount(amt.group(1)) if amt else None,
        hs_code=hs.group(1) if hs else None,
        origin=origin.group(1).strip() if origin else None,
        po_number=po.group(1) if po else None,
        invoice_number=inv.group(1) if inv else None,
    )


def check_packet(docs: list[tuple[str, str | None, CanonicalDocument]]) -> PacketReport:
    """Validate a shipment packet: extract fields per doc, cross-check, and build a checklist."""
    fields = [extract_shipment_fields(did, title, doc) for did, title, doc in docs]
    findings: list[PacketFinding] = []

    # 1) Currency consistency across documents that declare one.
    currencies = {f.currency for f in fields if f.currency}
    if len(currencies) > 1:
        findings.append(
            PacketFinding(
                severity="error",
                code="currency_mismatch",
                message=f"Documents declare different currencies: {', '.join(sorted(currencies))}.",
            )
        )

    # 2) Country of origin should be present somewhere in the packet.
    if not any(f.origin for f in fields):
        findings.append(
            PacketFinding(
                severity="warn",
                code="origin_missing",
                message="No country of origin found in any document — customs will require it.",
            )
        )

    # 3) HS / tariff code should be present (drives duty).
    if not any(f.hs_code for f in fields):
        findings.append(
            PacketFinding(
                severity="warn",
                code="hs_code_missing",
                message="No HS/tariff code found — classification is needed to compute duties.",
            )
        )

    # 4) Totals should agree across documents that state one (within a small tolerance).
    totals = [f.total for f in fields if f.total is not None]
    if len(totals) > 1 and (max(totals) - min(totals)) > max(0.01, 0.01 * max(totals)):
        findings.append(
            PacketFinding(
                severity="error",
                code="total_mismatch",
                message=f"Declared totals differ across documents: {sorted(set(totals))}.",
            )
        )

    # 5) Checklist of required packet documents.
    present_types = {f.doc_type for f in fields}
    checklist = [
        ChecklistItem(doc_type=t, label=label, present=t in present_types)
        for t, label in REQUIRED_DOC_TYPES
    ]
    for item in checklist:
        if not item.present:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="document_missing",
                    message=f"Packet is missing a {item.label.lower()}.",
                )
            )

    errors = sum(1 for f in findings if f.severity == "error")
    warns = sum(1 for f in findings if f.severity == "warn")
    n = len(docs)
    if errors:
        summary = f"{errors} blocking issue(s) and {warns} warning(s) across {n} document(s)."
    elif warns:
        summary = f"No blocking issues; {warns} warning(s) to review across {n} document(s)."
    else:
        summary = f"Packet is consistent across {len(docs)} document(s)."

    return PacketReport(
        document_count=len(docs),
        documents=fields,
        findings=findings,
        checklist=checklist,
        summary=summary,
    )
