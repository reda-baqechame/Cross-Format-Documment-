"""Insurance pack — deterministic policy/declarations review over the canonical model.

Insurance documents hide expensive surprises: a lapsed policy, a coverage limit below what's
required, a missing deductible, or a claim filed outside the coverage window. This extracts the key
declarations-page fields (policy number, insurer/insured, coverage limit, premium, deductible,
effective/expiration dates) deterministically from the redaction-aware visible text and flags
common risks — offline, no LLM. When a claim and its policy are reviewed together, it checks the
claim falls within the policy period.

Reuses the shared finding/text helpers from the import/export pack so the packs stay consistent.
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.packs.import_export import PacketFinding, _visible_text

_POLICY_NO = re.compile(
    r"\bpolicy\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]{4,})", re.I
)
_CLAIM_NO = re.compile(r"\bclaim\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]{4,})", re.I)
_MONEY = r"([$€£]?\s?\d[\d,]*(?:\.\d{2})?)"
_COVERAGE = re.compile(
    r"(?:coverage\s*limit|limit\s*of\s*liability|sum\s*insured|coverage\s*amount)"
    r"[^.\n]{0,40}?" + _MONEY,
    re.I,
)
_PREMIUM = re.compile(r"(?:premium)[^.\n]{0,40}?" + _MONEY, re.I)
_DEDUCTIBLE = re.compile(r"(?:deductible|excess)[^.\n]{0,40}?" + _MONEY, re.I)
# Dates as YYYY-MM-DD or MM/DD/YYYY around effective/expiration labels.
_EFFECTIVE = re.compile(
    r"(?:effective\s*date|policy\s*period\s*from|inception)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)
_EXPIRATION = re.compile(
    r"(?:expiration\s*date|expiry|expires?|policy\s*period\s*to|valid\s*(?:un)?til)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)
_CLAIM_DATE = re.compile(
    r"(?:date\s*of\s*loss|loss\s*date|date\s*of\s*claim|incident\s*date)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)


class PolicyFields(BaseModel):
    doc_id: str
    title: str | None
    kind: str  # policy | claim | other
    policy_number: str | None = None
    claim_number: str | None = None
    coverage_limit: float | None = None
    premium: float | None = None
    deductible: float | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    claim_date: str | None = None


class InsuranceReport(BaseModel):
    document_count: int
    documents: list[PolicyFields]
    findings: list[PacketFinding]
    summary: str


def _amount(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", raw))
    except ValueError:
        return None


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        if "-" in raw:
            y, m, d = (int(x) for x in raw.split("-"))
            return date(y, m, d)
        m, d, y = (int(x) for x in raw.split("/"))
        if y < 100:
            y += 2000
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _kind(text: str) -> str:
    low = text.lower()
    if _CLAIM_NO.search(text) or "date of loss" in low or "claim form" in low:
        return "claim"
    if "policy" in low or "declarations" in low or "insured" in low or "premium" in low:
        return "policy"
    return "other"


def extract_policy_fields(doc_id: str, title: str | None, doc: CanonicalDocument) -> PolicyFields:
    """Pull declarations/claim fields from one insurance document (deterministic)."""
    text = _visible_text(doc)
    pol = _POLICY_NO.search(text)
    clm = _CLAIM_NO.search(text)
    cov = _COVERAGE.search(text)
    prem = _PREMIUM.search(text)
    ded = _DEDUCTIBLE.search(text)
    eff = _EFFECTIVE.search(text)
    exp = _EXPIRATION.search(text)
    cld = _CLAIM_DATE.search(text)
    return PolicyFields(
        doc_id=doc_id,
        title=title,
        kind=_kind(text),
        policy_number=pol.group(1) if pol else None,
        claim_number=clm.group(1) if clm else None,
        coverage_limit=_amount(cov.group(1)) if cov else None,
        premium=_amount(prem.group(1)) if prem else None,
        deductible=_amount(ded.group(1)) if ded else None,
        effective_date=eff.group(1) if eff else None,
        expiration_date=exp.group(1) if exp else None,
        claim_date=cld.group(1) if cld else None,
    )


def check_insurance(docs: list[tuple[str, str | None, CanonicalDocument]]) -> InsuranceReport:
    """Review insurance documents: per-policy risk flags + claim-within-period checks (offline)."""
    fields = [extract_policy_fields(did, title, doc) for did, title, doc in docs]
    policies = [f for f in fields if f.kind == "policy"]
    claims = [f for f in fields if f.kind == "claim"]
    findings: list[PacketFinding] = []

    today = date.today()
    for p in policies:
        exp = _parse_date(p.expiration_date)
        if exp is not None and exp < today:
            findings.append(
                PacketFinding(
                    severity="error",
                    code="policy_expired",
                    message=f"Policy {p.policy_number or p.doc_id} expired on {p.expiration_date}.",
                )
            )
        if p.coverage_limit is None:
            findings.append(
                PacketFinding(
                    severity="warn",
                    code="coverage_limit_missing",
                    message=f"Policy {p.policy_number or p.doc_id} has no stated coverage limit.",
                )
            )
        if p.deductible is None:
            findings.append(
                PacketFinding(
                    severity="info",
                    code="deductible_missing",
                    message=f"Policy {p.policy_number or p.doc_id} states no deductible.",
                )
            )

    # Claim-within-coverage-period: match a claim to a policy by policy number when present.
    pol_by_number = {p.policy_number: p for p in policies if p.policy_number}
    for c in claims:
        loss = _parse_date(c.claim_date)
        pol = pol_by_number.get(c.policy_number) if c.policy_number else None
        if pol is None and len(policies) == 1:
            pol = policies[0]
        if loss is not None and pol is not None:
            eff = _parse_date(pol.effective_date)
            exp = _parse_date(pol.expiration_date)
            if (eff is not None and loss < eff) or (exp is not None and loss > exp):
                findings.append(
                    PacketFinding(
                        severity="error",
                        code="claim_outside_coverage",
                        message=(
                            f"Claim {c.claim_number or c.doc_id} loss date {c.claim_date} falls "
                            f"outside the policy period ({pol.effective_date} – "
                            f"{pol.expiration_date})."
                        ),
                    )
                )

    errors = sum(1 for f in findings if f.severity == "error")
    n = len(docs)
    if errors:
        summary = f"{errors} blocking insurance issue(s) across {n} document(s)."
    else:
        summary = (
            f"{len(policies)} policy/policies, {len(claims)} claim(s); no blocking issues "
            f"across {n} document(s)."
        )
    return InsuranceReport(
        document_count=n,
        documents=fields,
        findings=findings,
        summary=summary,
    )
