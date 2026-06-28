"""HR / onboarding pack — offer-letter field extraction + onboarding-packet completeness.

Hiring generates a packet of documents that must all be present and consistent before a start date:
offer letter, tax/eligibility forms, agreements. This extracts the key offer terms (candidate, role,
start date, compensation, employment type) deterministically from the redaction-aware text, and
checks that the expected onboarding documents are present — offline, no LLM. Mirrors the
import/export packet checker, applied to hiring.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.packs.import_export import (
    ChecklistItem,
    PacketFinding,
    _visible_text,
)

# The canonical onboarding packet — documents a new hire usually needs (US-centric defaults).
REQUIRED_DOC_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("offer_letter", ("offer letter", "offer of employment", "we are pleased to offer")),
    ("eligibility_form", ("form i-9", "employment eligibility", "i-9")),
    ("tax_withholding", ("form w-4", "withholding", "w-4")),
    ("confidentiality_agreement", ("confidentiality", "non-disclosure", "nda", "proprietary")),
)

_ROLE = re.compile(
    r"(?:position\s+of|role\s+of|as\s+(?:a|an|our)|title\s*[:\-])\s+"
    r"([A-Z][A-Za-z /&\-]{2,40}?)(?:[.,;\n]|\s+(?:at|with|reporting|starting|effective))",
    re.I,
)
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
_EMP_TYPE = re.compile(
    r"\b(full[\-\s]?time|part[\-\s]?time|contract(?:or)?|temporary|intern)\b", re.I
)
_AT_WILL = re.compile(r"at[\-\s]?will", re.I)


class OfferFields(BaseModel):
    doc_id: str
    title: str | None
    role: str | None = None
    start_date: str | None = None
    compensation: str | None = None
    employment_type: str | None = None
    at_will: bool = False


class HRReport(BaseModel):
    document_count: int
    offers: list[OfferFields]
    findings: list[PacketFinding]
    checklist: list[ChecklistItem]
    summary: str


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .,;:-")


def _is_offer(text: str) -> bool:
    low = text.lower()
    return any(sig in low for sig in REQUIRED_DOC_TYPES[0][1])


def extract_offer_fields(doc_id: str, title: str | None, doc: CanonicalDocument) -> OfferFields:
    """Pull the key offer-letter terms from one document (deterministic, redaction-aware)."""
    text = _visible_text(doc)
    role = _ROLE.search(text)
    start = _START.search(text)
    sal = _SALARY.search(text)
    emp = _EMP_TYPE.search(text)
    return OfferFields(
        doc_id=doc_id,
        title=title,
        role=_clean(role.group(1)) if role else None,
        start_date=_clean(start.group(1)) if start else None,
        compensation=_clean(sal.group(1)) if sal else None,
        employment_type=_clean(emp.group(1)).lower().replace(" ", "-") if emp else None,
        at_will=bool(_AT_WILL.search(text)),
    )


def check_onboarding(docs: list[tuple[str, str | None, CanonicalDocument]]) -> HRReport:
    """Extract offer terms + verify onboarding-packet completeness (deterministic, offline)."""
    texts = {did: _visible_text(doc) for did, _, doc in docs}
    offers = [
        extract_offer_fields(did, title, doc)
        for did, title, doc in docs
        if _is_offer(texts[did])
    ]
    findings: list[PacketFinding] = []

    # Per-offer completeness — the terms a candidate needs before accepting.
    for o in offers:
        if not o.start_date:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="start_date_missing",
                    message=f"Offer {o.title or o.doc_id} has no start date.",
                )
            )
        if not o.compensation:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="compensation_missing",
                    message=f"Offer {o.title or o.doc_id} states no compensation.",
                )
            )

    # Packet completeness — which required onboarding documents are present.
    all_text = "\n".join(texts.values()).lower()
    checklist: list[ChecklistItem] = []
    for doc_type, signals in REQUIRED_DOC_TYPES:
        present = any(sig in all_text for sig in signals)
        label = doc_type.replace("_", " ").title()
        checklist.append(ChecklistItem(doc_type=doc_type, label=label, present=present))
        if not present:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="document_missing",
                    message=f"Onboarding packet is missing a {label.lower()}.",
                )
            )

    warns = sum(1 for f in findings if f.severity == "warn")
    n = len(docs)
    if warns:
        summary = f"{len(offers)} offer(s); {warns} onboarding gap(s) to resolve across {n} doc(s)."
    else:
        summary = f"{len(offers)} offer(s); onboarding packet complete across {n} document(s)."
    return HRReport(
        document_count=n,
        offers=offers,
        findings=findings,
        checklist=checklist,
        summary=summary,
    )
