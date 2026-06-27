"""PII scan entry point — selects + merges detection engines.

Routes call :func:`scan` instead of a specific engine. It always runs the high-precision regex
detector, and — when ``PII_ENGINE=presidio`` and Presidio is installed — augments it with Presidio's
NER findings, de-duplicated by ``(node_id, category)`` so an overlapping hit (e.g. an email found by
both) is never counted twice. With the default engine this is exactly the regex behaviour, so the
offline default and existing flows are unchanged.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.provenance.sensitive import SensitiveFinding, scan_document
from docos.settings import get_settings


def _merge(
    regex_findings: list[SensitiveFinding], extra: list[SensitiveFinding]
) -> list[SensitiveFinding]:
    seen = {(f.node_id, f.category) for f in regex_findings}
    merged = list(regex_findings)
    for f in extra:
        if (f.node_id, f.category) in seen:
            continue
        seen.add((f.node_id, f.category))
        merged.append(f)
    return merged


def scan(doc: CanonicalDocument) -> list[SensitiveFinding]:
    """Detect sensitive values, augmenting regex hits with Presidio NER when configured."""
    findings = scan_document(doc)
    if get_settings().pii_engine == "presidio":
        from docos.services.provenance.presidio import presidio_available, presidio_findings

        if presidio_available():
            findings = _merge(findings, presidio_findings(doc))
    return findings
