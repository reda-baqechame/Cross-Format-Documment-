"""Per-type analyzers + the dispatcher that picks the right one.

Each analyzer is a pure function over the canonical model (already classified and
entity-extracted) that returns a ``DocumentInsight``. Add a new document kind by
writing one function and registering it in ``_REGISTRY`` — the capability is built
once over the shared model, never per-format.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic import classify as classify_service
from docos.services.semantic import extract as extract_service
from docos.services.semantic.classify import Classification
from docos.services.semantic.extract import Extraction
from docos.services.semantic.intelligence.base import (
    Analyzer,
    DocumentInsight,
    InsightCheck,
    InsightField,
    blank_lines,
    entities_of,
    field_nodes,
    find_field,
    first_entity,
    has_any,
    node_text,
    nodes_of_type,
    score_summary,
    to_amount,
    visible_lines,
    visible_text,
)

_RECONCILE_TOLERANCE = 0.02


def _field(key: str, found, *, confidence: float = 0.9) -> InsightField | None:
    if found is None:
        return None
    return InsightField(
        key=key, value=found.value, node_id=getattr(found, "node_id", None), confidence=confidence
    )


def _collect(*fields: InsightField | None) -> list[InsightField]:
    return [f for f in fields if f is not None]


def analyze_invoice(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    number = find_field(extraction, "invoice number", "invoice no", "invoice #", "invoice id")
    inv_date = find_field(extraction, "invoice date", "date of issue", "issued")
    due = find_field(extraction, "due date", "payment due")
    bill_to = find_field(extraction, "bill to", "customer", "client", "sold to")
    vendor = find_field(extraction, "vendor", "seller", "supplier")
    total = find_field(
        extraction,
        "total due",
        "amount due",
        "balance due",
        "grand total",
        "total",
        exclude=("subtotal", "sub total", "sub-total"),
    )
    subtotal = find_field(extraction, "subtotal", "sub total", "sub-total")
    tax = find_field(extraction, "tax", "vat", "gst", "sales tax")

    money = entities_of(extraction, "money")
    fields = _collect(
        _field("invoice_number", number),
        _field("invoice_date", inv_date),
        _field("due_date", due),
        _field("bill_to", bill_to),
        _field("vendor", vendor),
        _field("subtotal", subtotal),
        _field("tax", tax),
        _field("total", total),
    )

    checks: list[InsightCheck] = []
    has_total = total is not None or bool(money)
    checks.append(
        InsightCheck(
            id="has_total",
            label="Total amount present",
            severity="error",
            passed=has_total,
            detail="No total or monetary amount found — the bill is unusable without it."
            if not has_total
            else "",
        )
    )
    checks.append(
        InsightCheck(
            id="has_invoice_number",
            label="Invoice number present",
            severity="warn",
            passed=number is not None,
            detail="No invoice number — hard to reference for payment or disputes."
            if number is None
            else "",
        )
    )
    checks.append(
        InsightCheck(
            id="has_due_date",
            label="Due date present",
            severity="warn",
            passed=due is not None,
            detail="No due date — payment terms are ambiguous." if due is None else "",
        )
    )
    checks.append(
        InsightCheck(
            id="has_bill_to",
            label="Recipient (bill-to) present",
            severity="info",
            passed=bill_to is not None,
        )
    )

    # The high-value check: do the numbers actually add up?
    sub_amt = to_amount(subtotal.value) if subtotal else None
    tax_amt = to_amount(tax.value) if tax else 0.0
    total_amt = to_amount(total.value) if total else None
    if sub_amt is not None and total_amt is not None:
        expected = sub_amt + (tax_amt or 0.0)
        ok = abs(expected - total_amt) <= max(_RECONCILE_TOLERANCE, abs(total_amt) * 0.005)
        checks.append(
            InsightCheck(
                id="totals_reconcile",
                label="Subtotal + tax = total",
                severity="error",
                passed=ok,
                detail=""
                if ok
                else f"Subtotal {sub_amt:.2f} + tax {(tax_amt or 0.0):.2f} = "
                f"{expected:.2f}, but total reads {total_amt:.2f}.",
            )
        )

    return DocumentInsight(
        doc_type="invoice",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=score_summary("invoice", checks),
    )


def analyze_receipt(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    merchant = find_field(extraction, "merchant", "store", "sold by", "vendor")
    date = find_field(extraction, "date") or first_entity(extraction, "date")
    total = find_field(extraction, "total", "amount paid", "amount", "grand total")
    payment = find_field(extraction, "payment", "paid by", "card", "method")
    tax = find_field(extraction, "tax", "vat", "gst")

    money = entities_of(extraction, "money")
    fields = _collect(
        _field("merchant", merchant),
        _field("date", date),
        _field("payment_method", payment),
        _field("tax", tax),
        _field("total", total),
    )
    checks = [
        InsightCheck(
            id="has_total",
            label="Amount present",
            severity="error",
            passed=total is not None or bool(money),
        ),
        InsightCheck(
            id="has_date",
            label="Date present",
            severity="warn",
            passed=date is not None,
            detail="No date — receipts need one for expense/tax claims." if date is None else "",
        ),
        InsightCheck(
            id="has_merchant",
            label="Merchant present",
            severity="info",
            passed=merchant is not None,
        ),
    ]
    return DocumentInsight(
        doc_type="receipt",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=score_summary("receipt", checks),
    )


_CLAUSES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("termination", "Termination clause", "warn", ("terminat",)),
    (
        "confidentiality",
        "Confidentiality clause",
        "warn",
        ("confidential", "non-disclosure", "nondisclosure"),
    ),
    (
        "liability",
        "Liability / indemnification clause",
        "warn",
        ("liability", "indemnif", "hold harmless"),
    ),
    ("governing_law", "Governing-law clause", "warn", ("governing law", "jurisdiction")),
    (
        "signature",
        "Signature block",
        "error",
        ("signature", "signed by", "in witness whereof", "/s/"),
    ),
    ("payment", "Payment / consideration terms", "info", ("payment", "fees", "compensation")),
)

# Risky language: passed == True means the risky phrasing is *absent*.
_RISKS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("no_unlimited_liability", "No unlimited-liability language", "warn", ("unlimited liability",)),
    (
        "no_auto_renew",
        "No silent auto-renewal",
        "info",
        ("auto-renew", "automatically renew", "automatically renews"),
    ),
    ("no_perpetual", "No perpetual term", "info", ("perpetual", "in perpetuity")),
)


def analyze_contract(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    text = visible_text(doc).lower()
    effective = find_field(extraction, "effective date", "dated", "date")
    term = find_field(extraction, "term", "duration")
    law = find_field(extraction, "governing law", "jurisdiction")

    parties = None
    for _id, line in visible_lines(doc):
        low = line.lower()
        if "by and between" in low or "between" in low and " and " in low:
            parties = InsightField(key="parties", value=line.strip()[:200], node_id=_id)
            break

    fields = _collect(
        parties,
        _field("effective_date", effective),
        _field("term", term),
        _field("governing_law", law),
    )

    checks: list[InsightCheck] = []
    for cid, label, severity, terms in _CLAUSES:
        present = has_any(text, *terms)
        checks.append(
            InsightCheck(
                id=f"clause_{cid}",
                label=label,
                severity=severity,
                passed=present,
                detail="" if present else f"No {label.lower()} detected.",
            )
        )
    for rid, label, severity, terms in _RISKS:
        risky = has_any(text, *terms)
        checks.append(
            InsightCheck(
                id=rid,
                label=label,
                severity=severity,
                passed=not risky,
                detail=f"Found: {next(t for t in terms if t in text)!r}." if risky else "",
            )
        )

    return DocumentInsight(
        doc_type="contract",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=score_summary("contract", checks),
    )


_RESUME_SECTIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("experience", "Work experience", "warn", ("experience", "employment", "work history")),
    ("education", "Education", "warn", ("education", "degree", "university", "b.sc", "b.a")),
    ("skills", "Skills", "warn", ("skills", "technologies", "proficiencies")),
    ("summary", "Summary / objective", "info", ("summary", "objective", "profile")),
)


def analyze_resume(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    text = visible_text(doc)
    low = text.lower()
    email = first_entity(extraction, "email")
    phone = first_entity(extraction, "phone")
    dates = entities_of(extraction, "date")

    name = None
    lines = visible_lines(doc)
    if lines:
        name = InsightField(key="name", value=lines[0][1].strip()[:120], node_id=lines[0][0])

    fields = _collect(
        name,
        _field("email", email) if email else None,
        _field("phone", phone) if phone else None,
    )

    checks: list[InsightCheck] = [
        InsightCheck(
            id="has_email",
            label="Contact email present",
            severity="error",
            passed=email is not None,
            detail="No email — most applicant-tracking systems reject or can't route this."
            if email is None
            else "",
        ),
        InsightCheck(
            id="has_phone",
            label="Phone number present",
            severity="warn",
            passed=phone is not None,
        ),
    ]
    for sid, label, severity, terms in _RESUME_SECTIONS:
        present = has_any(low, *terms)
        checks.append(
            InsightCheck(
                id=f"section_{sid}",
                label=f"{label} section",
                severity=severity,
                passed=present,
                detail="" if present else f"No {label.lower()} section found.",
            )
        )
    checks.append(
        InsightCheck(
            id="has_dates",
            label="Dated history (employment/education)",
            severity="info",
            passed=bool(dates),
        )
    )
    words = len(text.split())
    checks.append(
        InsightCheck(
            id="length_reasonable",
            label="Reasonable length",
            severity="warn",
            passed=words >= 120,
            detail=f"Only {words} words — likely too sparse for a full résumé."
            if words < 120
            else "",
        )
    )

    return DocumentInsight(
        doc_type="resume",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=score_summary("resume", checks),
    )


def analyze_form(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    """Forms & applications: enumerate fillable fields and flag what's still blank
    or unsigned — the job a form actually needs done before it's submitted."""
    nodes = field_nodes(doc)
    blanks = blank_lines(doc)
    text = visible_text(doc).lower()

    filled = [n for n in nodes if (getattr(n, "value", None) or "").strip()]
    empty = [n for n in nodes if not (getattr(n, "value", None) or "").strip()]

    fields: list[InsightField] = []
    for n in nodes:
        value = (getattr(n, "value", None) or "").strip()
        fields.append(
            InsightField(
                key=getattr(n, "field_name", "") or "field",
                value=value or "(blank)",
                node_id=n.id,
                confidence=1.0,
            )
        )
    for node_id, label in blanks[:20]:
        fields.append(InsightField(key=label or "blank", value="(blank)", node_id=node_id))

    total_blanks = len(empty) + len(blanks)
    has_fields = bool(nodes or blanks)
    checks: list[InsightCheck] = [
        InsightCheck(
            id="has_fields",
            label="Fillable fields detected",
            severity="error",
            passed=has_fields,
            detail="No form fields or blanks found — nothing to fill." if not has_fields else "",
        ),
        InsightCheck(
            id="all_required_filled",
            label="All fields completed",
            severity="warn",
            passed=has_fields and total_blanks == 0,
            detail=(
                f"{total_blanks} field(s) still blank"
                + (
                    ": " + ", ".join([getattr(n, "field_name", "field") for n in empty][:5])
                    if empty
                    else ""
                )
                if total_blanks
                else ""
            ),
        ),
        InsightCheck(
            id="has_signature",
            label="Signature line present",
            severity="warn",
            passed=has_any(text, "signature", "signed", "sign here")
            or any(getattr(n, "field_kind", "") == "signature" for n in nodes),
        ),
        InsightCheck(
            id="has_date",
            label="Date field present",
            severity="info",
            passed=has_any(text, "date")
            or any(getattr(n, "field_kind", "") == "date" for n in nodes),
        ),
    ]
    summary = (
        f"Form: {len(filled)}/{len(filled) + total_blanks} fields completed"
        if has_fields
        else "No fillable fields detected."
    )
    return DocumentInsight(
        doc_type="form",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=summary if has_fields else score_summary("form", checks),
    )


# Investor/sales pitch-deck completeness — the classic narrative arc.
_DECK_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("problem", "Problem", ("problem", "pain", "challenge")),
    ("solution", "Solution", ("solution", "product", "how it works")),
    ("market", "Market size", ("market", "tam", "opportunity")),
    ("model", "Business model", ("business model", "pricing", "revenue", "monetiz")),
    ("traction", "Traction", ("traction", "growth", "users", "revenue")),
    ("team", "Team", ("team", "founder", "about us")),
    ("ask", "The ask", ("ask", "raising", "investment", "funding", "use of funds")),
)


def analyze_presentation(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    """Slide decks & pitch decks: title slide, slide count, agenda/closing, and a
    pitch-deck completeness checklist (problem→solution→market→…→ask)."""
    pages = nodes_of_type(doc, "page")
    heading_nodes = nodes_of_type(doc, "heading")
    titles = [t for t in (node_text(doc, h) for h in heading_nodes) if t]
    text = visible_text(doc).lower()
    slide_count = len(pages) or len(heading_nodes) or 1

    fields: list[InsightField] = []
    if titles:
        fields.append(InsightField(key="title", value=titles[0][:120], node_id=None))
    fields.append(InsightField(key="slide_count", value=str(slide_count), node_id=None))
    for t in titles[1:9]:
        fields.append(InsightField(key="section", value=t[:80], node_id=None))

    checks: list[InsightCheck] = [
        InsightCheck(
            id="has_title_slide",
            label="Title slide present",
            severity="error",
            passed=bool(titles),
            detail="No title/heading found to open the deck." if not titles else "",
        ),
        InsightCheck(
            id="slide_count_reasonable",
            label="Reasonable slide count",
            severity="warn",
            passed=3 <= slide_count <= 60,
            detail=(
                f"{slide_count} slides — decks usually run 5–30."
                if not 3 <= slide_count <= 60
                else ""
            ),
        ),
        InsightCheck(
            id="has_agenda_or_closing",
            label="Agenda or closing slide",
            severity="info",
            passed=has_any(text, "agenda", "next steps", "thank you", "q&a", "summary"),
        ),
    ]

    # If it reads like a pitch, score the investor-deck narrative arc.
    looks_like_pitch = has_any(
        text, "pitch", "investor", "raising", "seed", "series a", "valuation", "tam"
    )
    if looks_like_pitch:
        for sid, label, terms in _DECK_SECTIONS:
            present = has_any(text, *terms)
            checks.append(
                InsightCheck(
                    id=f"deck_has_{sid}",
                    label=f"{label} slide",
                    severity="warn",
                    passed=present,
                    detail="" if present else f"No {label.lower()} content detected.",
                )
            )

    return DocumentInsight(
        doc_type="presentation",
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=score_summary("presentation", checks),
    )


def analyze_generic(
    doc: CanonicalDocument, classification: Classification, extraction: Extraction
) -> DocumentInsight:
    """Fallback for kinds without a dedicated analyzer: surface the strongest
    extracted fields and a quick inventory of detected entities."""
    fields = [
        InsightField(key=f.key, value=f.value, node_id=f.node_id, confidence=0.6)
        for f in extraction.fields[:8]
    ]
    counts = {
        etype: len(entities_of(extraction, etype))
        for etype in ("date", "money", "email", "phone")
    }
    checks = [
        InsightCheck(
            id=f"found_{etype}",
            label=f"{etype.capitalize()} values detected",
            severity="info",
            passed=count > 0,
            detail=f"{count} found." if count else "",
        )
        for etype, count in counts.items()
    ]
    label = classification.label if classification.label != "other" else "document"
    return DocumentInsight(
        doc_type=label,
        confidence=classification.confidence,
        fields=fields,
        checks=checks,
        summary=f"Detected as {label}. {sum(counts.values())} data values extracted.",
    )


_REGISTRY: dict[str, Analyzer] = {
    "invoice": analyze_invoice,
    "receipt": analyze_receipt,
    "contract": analyze_contract,
    "resume": analyze_resume,
    "form": analyze_form,
    "presentation": analyze_presentation,
}


def analyze(doc: CanonicalDocument) -> DocumentInsight:
    """Classify the document, extract entities, then run the matching typed analyzer."""
    classification = classify_service.classify(doc)
    extraction = extract_service.extract(doc)
    analyzer = _REGISTRY.get(classification.label, analyze_generic)
    return analyzer(doc, classification, extraction)
