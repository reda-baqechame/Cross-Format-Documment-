"""Renewal tracking — suggest due dates from a document, classify urgency.

Date suggestions reuse the deterministic entity extractor (no AI required): every date found in the
document is normalised to ISO ``YYYY-MM-DD`` and offered as a candidate renewal/expiry date. Urgency
is a pure function of the due date relative to today.
"""

from __future__ import annotations

from datetime import date, datetime

from docos.model.document import CanonicalDocument
from docos.services.semantic.extract import extract

# Formats the entity extractor's date regex can produce.
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%b %d %Y", "%B %d, %Y")

# Window (days) within which an upcoming renewal is flagged "soon".
SOON_DAYS = 30


def normalise_date(raw: str) -> str | None:
    """Parse a date string in any extractor-produced format to ISO ``YYYY-MM-DD`` (or ``None``)."""
    text = raw.strip().replace(".", "")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def suggest_due_dates(doc: CanonicalDocument, *, today: date | None = None) -> list[str]:
    """ISO dates found in the document, de-duplicated, future-first then sorted ascending."""
    today = today or date.today()
    seen: set[str] = set()
    for entity in extract(doc).entities:
        if entity.type != "date":
            continue
        iso = normalise_date(entity.value)
        if iso and iso not in seen:
            seen.add(iso)
    future = sorted(d for d in seen if d >= today.isoformat())
    past = sorted((d for d in seen if d < today.isoformat()), reverse=True)
    return future + past


def urgency(due_date: str, *, today: date | None = None) -> str:
    """Classify a due date as ``overdue`` | ``soon`` | ``later`` relative to today."""
    today = today or date.today()
    try:
        due = date.fromisoformat(due_date)
    except ValueError:
        return "later"
    if due < today:
        return "overdue"
    if (due - today).days <= SOON_DAYS:
        return "soon"
    return "later"
