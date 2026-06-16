"""Sensitive-data detection — scan the canonical model for PII/secrets.

The trust incumbents (Litera Metadact, Office Document Inspector, …) are rule-based
and operate per-format; this scanner runs once over the canonical model, so a single
pass covers TXT, DOCX, PDF, XLSX, PPTX and OCR'd scans alike. Each hit maps to a node
id, so a detection can be turned straight into the existing node-level ``redact`` op —
true removal on export, fully reversible and audited like every other edit.

Detectors are intentionally high-precision (e.g. card numbers are Luhn-checked) so the
"clean before export" flow proposes redactions a user can trust. The matched value is
never echoed back verbatim — :func:`_mask` reveals only the last few characters.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted

# Ordered by priority: the first detector to claim a span wins, so a 16-digit card is
# never also reported as a phone number. Each entry is (category, compiled pattern).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("us_ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Candidate card: 13–19 digits, optionally grouped by single spaces/dashes.
    ("credit_card", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?<=\d)")),
    (
        "phone",
        re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)"),
    ),
    (
        "ipv4",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
        ),
    ),
]

# Human-readable labels for UI / audit detail.
CATEGORY_LABELS: dict[str, str] = {
    "email": "Email address",
    "us_ssn": "US Social Security number",
    "credit_card": "Payment card number",
    "phone": "Phone number",
    "ipv4": "IP address",
}


class SensitiveFinding(BaseModel):
    """One detected sensitive value, located at a single node."""

    node_id: str
    category: str
    label: str
    excerpt: str  # masked — never the raw secret


def _luhn_ok(digits: str) -> bool:
    """True if ``digits`` passes the Luhn checksum (card-number sanity check)."""
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask(value: str) -> str:
    """Reveal the last few alphanumerics; mask the rest. Separators are preserved."""
    keep = 2 if len(value.replace(" ", "")) <= 6 else 4
    out: list[str] = []
    revealed = 0
    for ch in reversed(value):
        if ch.isalnum():
            if revealed < keep:
                out.append(ch)
                revealed += 1
            else:
                out.append("•")
        else:
            out.append(ch)
    return "".join(reversed(out))


def _scan_text(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(category, matched_value)`` for non-overlapping detections in ``text``."""
    claimed: list[tuple[int, int]] = []  # spans already taken by a higher-priority detector

    def overlaps(start: int, end: int) -> bool:
        return any(start < c_end and end > c_start for c_start, c_end in claimed)

    for category, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            if overlaps(start, end):
                continue
            value = m.group()
            if category == "credit_card" and not _luhn_ok(re.sub(r"\D", "", value)):
                continue  # digit run that isn't a real card — leave the span free
            claimed.append((start, end))
            yield category, value


def scan_document(doc: CanonicalDocument) -> list[SensitiveFinding]:
    """Find sensitive values across every text-bearing node not already redacted."""
    findings: list[SensitiveFinding] = []
    for node in doc.nodes.values():
        text = getattr(node, "text", "")
        if not text or is_redacted(doc, node.id):
            continue
        for category, value in _scan_text(text):
            findings.append(
                SensitiveFinding(
                    node_id=node.id,
                    category=category,
                    label=CATEGORY_LABELS.get(category, category),
                    excerpt=_mask(value),
                )
            )
    return findings


def summarize(findings: list[SensitiveFinding]) -> dict[str, int]:
    """Count detections per category (for the response summary / audit detail)."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
    return counts


def redaction_node_ids(findings: list[SensitiveFinding]) -> list[str]:
    """Distinct node ids to redact, in first-seen order."""
    seen: dict[str, None] = {}
    for f in findings:
        seen.setdefault(f.node_id, None)
    return list(seen)
