"""Shared types and helpers for typed document intelligence.

A ``DocumentInsight`` is the typed, validated read of a document for a specific
purpose (invoice, contract, résumé, …): the fields that matter *for that kind of
document*, plus actionable ``checks`` that verify the document actually does its
job — e.g. an invoice's subtotal + tax reconciling to its total, or a résumé
carrying a contact email. Everything here is deterministic and redaction-aware:
text that has been redacted is never read, so a redacted total fails its check
rather than leaking.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.semantic.classify import Classification
from docos.services.semantic.extract import Extraction

# Severity ladder for a check. ``error`` is a real problem with the document,
# ``warn`` is likely-missing/risky, ``info`` is advisory.
Severity = str


class InsightField(BaseModel):
    """A typed value pulled for this document kind, with node-level provenance."""

    key: str
    value: str
    node_id: str | None = None
    confidence: float = 1.0


class InsightCheck(BaseModel):
    """An actionable verification. ``passed`` is True when the document is in the
    good/desired state (clause present, totals reconcile, contact email found)."""

    id: str
    label: str
    severity: Severity
    passed: bool
    detail: str = ""


class DocumentInsight(BaseModel):
    doc_type: str
    confidence: float
    fields: list[InsightField]
    checks: list[InsightCheck]
    summary: str


# An analyzer turns a classified, extracted document into a typed insight.
Analyzer = Callable[[CanonicalDocument, Classification, Extraction], DocumentInsight]


def visible_lines(doc: CanonicalDocument) -> list[tuple[str, str]]:
    """``(node_id, text)`` for every non-redacted text node, in reading order."""
    out: list[tuple[str, str]] = []
    for node in doc.walk():
        text = (getattr(node, "text", "") or "").strip()
        if text and not is_redacted(doc, node.id):
            out.append((node.id, text))
    return out


def visible_text(doc: CanonicalDocument) -> str:
    return "\n".join(text for _id, text in visible_lines(doc))


def find_field(extraction: Extraction, *names: str, exclude: tuple[str, ...] = ()):
    """First extracted ``Label: value`` field whose key contains one of ``names``
    and none of ``exclude`` (so "total" doesn't accidentally match "subtotal")."""
    for field in extraction.fields:
        key = field.key.lower()
        if any(bad in key for bad in exclude):
            continue
        if any(name in key for name in names):
            return field
    return None


def first_entity(extraction: Extraction, etype: str):
    for entity in extraction.entities:
        if entity.type == etype:
            return entity
    return None


def entities_of(extraction: Extraction, etype: str):
    return [e for e in extraction.entities if e.type == etype]


def field_nodes(doc: CanonicalDocument):
    """``FieldNode`` placeholders (form fields / template slots), redaction-aware."""
    return [
        node
        for node in doc.walk()
        if getattr(node, "type", "") == "field" and not is_redacted(doc, node.id)
    ]


def nodes_of_type(doc: CanonicalDocument, *types: str):
    """All non-redacted nodes whose ``type`` is one of ``types`` (in reading order)."""
    return [
        node
        for node in doc.walk()
        if getattr(node, "type", "") in types and not is_redacted(doc, node.id)
    ]


def node_text(doc: CanonicalDocument, node) -> str:
    """Concatenated non-redacted text of a node's child runs (e.g. a heading's text)."""
    parts: list[str] = []
    for child_id in getattr(node, "children", []) or []:
        child = doc.get(child_id)
        if child is None:
            continue
        text = getattr(child, "text", "")
        if text and not is_redacted(doc, child.id):
            parts.append(text)
    return " ".join(parts).strip()


_BLANK = re.compile(r"_{3,}|\.{4,}|\[\s*\]|\(\s*\)")


def blank_lines(doc: CanonicalDocument) -> list[tuple[str, str]]:
    """``(node_id, label)`` for lines that look like an unfilled fill-in blank
    ("Name: ____", "Signature ........"). Redaction-aware."""
    out: list[tuple[str, str]] = []
    for node_id, text in visible_lines(doc):
        if _BLANK.search(text):
            label = _BLANK.split(text)[0].strip(" :\t-") or text.strip()
            out.append((node_id, label[:60]))
    return out


_AMOUNT = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def to_amount(value: str) -> float | None:
    """Parse a numeric amount out of a money-ish string ("$1,234.50" -> 1234.5)."""
    match = _AMOUNT.search(value.replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def has_any(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def score_summary(doc_type: str, checks: list[InsightCheck]) -> str:
    """One-line headline: how many checks passed and how many real problems remain."""
    passed = sum(1 for c in checks if c.passed)
    errors = sum(1 for c in checks if not c.passed and c.severity == "error")
    warns = sum(1 for c in checks if not c.passed and c.severity == "warn")
    head = f"{doc_type.capitalize()}: {passed}/{len(checks)} checks passed"
    if errors:
        return f"{head} — {errors} problem(s) need attention."
    if warns:
        return f"{head} — {warns} thing(s) to review."
    return f"{head} — looks complete."
