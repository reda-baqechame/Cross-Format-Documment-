"""Contracts / CLM pack — deterministic clause extraction + risk review over the canonical model.

Contract review is slow, expensive, and error-prone: missed auto-renewals, absent liability caps,
and silent governing-law gaps cost real money. This pulls the key commercial terms from a contract
(parties, effective date, term, governing law, renewal, termination notice, liability cap, payment
terms) deterministically from the redaction-aware visible text and flags common risks — offline,
no LLM. An LLM pass can enrich this later, but the deterministic core always runs.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.packs.import_export import PacketFinding, _visible_text

_PARTIES = re.compile(
    r"\bbetween\s+(.+?)\s+(?:and|&)\s+(.+?)(?:[.,;]|\s+\(|\s+dated|\s+effective|$)",
    re.I,
)
_EFFECTIVE = re.compile(
    r"(?:effective\s*date|effective\s*as\s*of|dated)\s*[:\-]?\s*"
    r"([A-Za-z0-9,\s/\-]{6,30}?)(?:[.;\n]|$)",
    re.I,
)
_TERM = re.compile(
    r"\b(?:term\s+of|for\s+a\s+(?:period\s+of\s+)?|period\s+of)\s+"
    r"([a-z0-9()\-\s]{2,30}?\b(?:year|years|month|months|day|days))",
    re.I,
)
# "governed by the laws of [the State of] X" / "governing law ... laws of X" / "laws of X govern".
_GOVERNING = re.compile(
    r"govern(?:ed|ing)?[^.]{0,40}?laws?\s+of\s+(?:the\s+)?(?:state\s+of\s+|commonwealth\s+of\s+)?"
    r"([A-Z][A-Za-z .]{2,30})",
    re.I,
)
_GOVERNING2 = re.compile(
    r"laws?\s+of\s+(?:the\s+)?(?:state\s+of\s+)?([A-Z][A-Za-z .]{2,30})\s+(?:shall\s+)?govern",
    re.I,
)
_AUTO_RENEW = re.compile(
    r"automatically\s+renew|auto[\-\s]?renew|renew\s+automatically|"
    r"renewed?\s+for\s+(?:successive|additional)",
    re.I,
)
# Termination notice in days; tolerates a spelled-out number before a parenthetical "(30) days".
_TERMINATION = re.compile(
    r"terminat\w+[^.]{0,80}?(\d{1,3})\s*\)?\s*(?:calendar\s+|business\s+)?days",
    re.I,
)
_LIABILITY = re.compile(
    r"(?:liability[^.]{0,40}?(?:shall\s+not\s+exceed|limited\s+to|cap(?:ped)?)"
    r"|limit\w*\s+of\s+liability)",
    re.I,
)
_PAYMENT = re.compile(r"\b(net\s*\d{1,3})\b", re.I)


class ContractFields(BaseModel):
    doc_id: str
    title: str | None
    parties: list[str] = []
    effective_date: str | None = None
    term: str | None = None
    governing_law: str | None = None
    auto_renew: bool = False
    termination_notice_days: int | None = None
    has_liability_cap: bool = False
    payment_terms: str | None = None


class ContractReport(BaseModel):
    document_count: int
    documents: list[ContractFields]
    findings: list[PacketFinding]
    summary: str


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .,;:-")


def extract_contract_fields(
    doc_id: str, title: str | None, doc: CanonicalDocument
) -> ContractFields:
    """Pull the key commercial terms from one contract (deterministic, redaction-aware)."""
    text = _visible_text(doc)

    parties: list[str] = []
    m = _PARTIES.search(text)
    if m:
        parties = [_clean(m.group(1)), _clean(m.group(2))]
        parties = [p for p in parties if 1 < len(p) <= 80]

    eff = _EFFECTIVE.search(text)
    term = _TERM.search(text)
    gov = _GOVERNING.search(text) or _GOVERNING2.search(text)
    term_notice = _TERMINATION.search(text)
    pay = _PAYMENT.search(text)

    return ContractFields(
        doc_id=doc_id,
        title=title,
        parties=parties,
        effective_date=_clean(eff.group(1)) if eff else None,
        term=_clean(term.group(1)) if term else None,
        governing_law=_clean(gov.group(1)) if gov else None,
        auto_renew=bool(_AUTO_RENEW.search(text)),
        termination_notice_days=int(term_notice.group(1)) if term_notice else None,
        has_liability_cap=bool(_LIABILITY.search(text)),
        payment_terms=pay.group(1).title().replace(" ", " ") if pay else None,
    )


def _review(f: ContractFields) -> list[PacketFinding]:
    findings: list[PacketFinding] = []
    if not f.governing_law:
        findings.append(
            PacketFinding(
                severity="warn",
                code="governing_law_missing",
                message="No governing-law clause found — disputes have no agreed jurisdiction.",
            )
        )
    if f.auto_renew:
        findings.append(
            PacketFinding(
                severity="warn",
                code="auto_renewal",
                message="Contract auto-renews — confirm the notice window before it locks in.",
            )
        )
    if f.termination_notice_days is None:
        findings.append(
            PacketFinding(
                severity="warn",
                code="termination_notice_missing",
                message="No termination notice period found — exit terms are unclear.",
            )
        )
    if not f.has_liability_cap:
        findings.append(
            PacketFinding(
                severity="warn",
                code="liability_cap_missing",
                message="No limitation-of-liability clause found — exposure may be uncapped.",
            )
        )
    if not f.effective_date:
        findings.append(
            PacketFinding(
                severity="info",
                code="effective_date_missing",
                message="No effective date found — confirm when obligations begin.",
            )
        )
    return findings


def check_contracts(docs: list[tuple[str, str | None, CanonicalDocument]]) -> ContractReport:
    """Extract key terms per contract and flag common review risks (deterministic, offline)."""
    fields = [extract_contract_fields(did, title, doc) for did, title, doc in docs]
    findings: list[PacketFinding] = []
    for f in fields:
        findings.extend(_review(f))

    warns = sum(1 for x in findings if x.severity == "warn")
    n = len(docs)
    if warns:
        summary = f"{warns} risk(s) to review across {n} contract(s)."
    else:
        summary = f"No standard review risks found across {n} contract(s)."
    return ContractReport(
        document_count=n,
        documents=fields,
        findings=findings,
        summary=summary,
    )
