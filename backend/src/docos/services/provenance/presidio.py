"""Microsoft Presidio PII engine (MIT) — an activatable, default-off augmentation.

The built-in regex detector (`sensitive.py`) is high-precision but only catches structured patterns
(emails, SSNs, cards, phones, IPs). Presidio adds NER-based detection — names, locations, dates,
nationalities, medical terms, … — which is exactly what "redact all personal information" needs on
real prose. It is an *optional* dependency (``pip install presidio-analyzer`` + a spaCy model) and
activates only when ``PII_ENGINE=presidio`` and the package is importable; otherwise the platform
uses regex-only, unchanged.

The Presidio→finding mapping (:func:`map_results`) is pure and unit-tested, so it is covered without
the heavy native dependency installed. Presidio entity types are normalised to the regex categories
where they overlap, so merging the two engines never double-counts the same hit.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.provenance.sensitive import (
    CATEGORY_LABELS,
    SensitiveFinding,
    _mask,
)

# Map Presidio entity types onto our categories. Overlapping ones reuse the regex category (so the
# merge dedupes); NER-only ones get their own lowercased category + a friendly label.
_ENTITY_CATEGORY = {
    "EMAIL_ADDRESS": "email",
    "US_SSN": "us_ssn",
    "CREDIT_CARD": "credit_card",
    "PHONE_NUMBER": "phone",
    "IP_ADDRESS": "ipv4",
    "PERSON": "person",
    "LOCATION": "location",
    "DATE_TIME": "date_time",
    "NRP": "nationality",
    "MEDICAL_LICENSE": "medical_license",
    "IBAN_CODE": "iban",
    "US_DRIVER_LICENSE": "us_driver_license",
    "US_PASSPORT": "us_passport",
}
_EXTRA_LABELS = {
    "person": "Person name",
    "location": "Location",
    "date_time": "Date / time",
    "nationality": "Nationality / religion / group",
    "medical_license": "Medical license",
    "iban": "IBAN",
    "us_driver_license": "US driver license",
    "us_passport": "US passport",
}
# Below this Presidio score a detection is too weak to surface.
_MIN_SCORE = 0.5


def presidio_available() -> bool:
    """True when the optional ``presidio-analyzer`` package can be imported."""
    try:
        import presidio_analyzer  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency; absence is the common case
        return False
    return True


def map_results(node_id: str, text: str, results: list) -> list[SensitiveFinding]:
    """Map Presidio ``RecognizerResult``-like objects for one node into :class:`SensitiveFinding`s.

    Each result needs ``.entity_type``, ``.start``, ``.end`` and ``.score`` — exactly what Presidio
    emits. Pure so it can be tested with recorded results (no Presidio install required).
    """
    findings: list[SensitiveFinding] = []
    for r in results:
        if getattr(r, "score", 1.0) < _MIN_SCORE:
            continue
        entity = getattr(r, "entity_type", "")
        category = _ENTITY_CATEGORY.get(entity, entity.lower())
        value = text[getattr(r, "start", 0) : getattr(r, "end", 0)]
        if not value.strip():
            continue
        label = CATEGORY_LABELS.get(category) or _EXTRA_LABELS.get(category, category)
        findings.append(
            SensitiveFinding(node_id=node_id, category=category, label=label, excerpt=_mask(value))
        )
    return findings


def presidio_findings(doc: CanonicalDocument) -> list[SensitiveFinding]:
    """Run Presidio over every non-redacted text node. ``[]`` if Presidio isn't installed."""
    if not presidio_available():
        return []
    try:
        from presidio_analyzer import AnalyzerEngine
    except Exception:  # noqa: BLE001 - guarded by presidio_available, but stay defensive
        return []
    analyzer = AnalyzerEngine()
    findings: list[SensitiveFinding] = []
    for node in doc.nodes.values():
        text = getattr(node, "text", "")
        if not text or is_redacted(doc, node.id):
            continue
        try:
            results = analyzer.analyze(text=text, language="en")
        except Exception:  # noqa: BLE001 - a recognition failure is non-fatal
            continue
        findings.extend(map_results(node.id, text, results))
    return findings
