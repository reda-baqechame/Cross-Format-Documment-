"""Document Skills — the framework that turns a parsed document into a typed *object*.

A skill encapsulates one document *purpose* (invoice, contract, résumé, …): how to detect it,
which fields matter, what to validate, and what to recommend next. Skills are pure, deterministic
and offline; they reuse the shared extraction/redaction/sensitive services rather than per-format
pipelines. A new purpose is added by dropping one module into this package and registering it.

This is the "organize around the document, not the file extension" move the market rewards.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.semantic.extract import Extraction, extract

FieldStatus = ("found", "low_confidence", "missing")


class ExtractedField(BaseModel):
    name: str
    label: str
    value: str | None = None
    confidence: float = 0.0
    node_id: str | None = None
    status: str = "missing"  # found | low_confidence | missing


class SkillFinding(BaseModel):
    level: str  # pass | warn | fail (same vocabulary as the validation engine)
    code: str
    message: str


class RecommendedAction(BaseModel):
    id: str
    label: str
    # Each kind maps to an already-shipped capability the frontend can execute.
    kind: str  # export | redact | sign | navigate
    params: dict[str, str] = Field(default_factory=dict)


def document_text(doc: CanonicalDocument) -> str:
    """Lowercased, redaction-aware concatenation of the document's text (for detection)."""
    parts = [
        getattr(n, "text", "")
        for n in doc.walk()
        if getattr(n, "text", "") and not is_redacted(doc, n.id)
    ]
    return "\n".join(parts).lower()


def money_to_float(value: str | None) -> float | None:
    """Parse a currency-ish string ('$1,230.00', '1230 USD') into a float, or None."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# "Label: value" on a single line — re-scanned per line because the txt/markdown adapters group
# consecutive lines into one multi-line run (so extract()'s per-node match misses them).
_LINE_FIELD = re.compile(r"^\s*([A-Z][A-Za-z0-9 /._#-]{1,40}?)\s*[:\-]\s*(\S.{0,120}?)\s*$")


class FieldFinder:
    """Label-synonym field lookup (line-scanned) + entity fallback over :func:`extract.extract`."""

    def __init__(self, doc: CanonicalDocument) -> None:
        self.extraction: Extraction = extract(doc)
        # lowercased label -> (value, node_id), first occurrence wins
        self._by_label: dict[str, tuple[str, str]] = {}
        # ordered (label, value, node_id) as they appear — for generic key facts
        self.line_fields: list[tuple[str, str, str]] = []
        for node in doc.walk():
            text = getattr(node, "text", "") or ""
            if not text or is_redacted(doc, node.id):
                continue
            for line in text.splitlines():
                m = _LINE_FIELD.match(line)
                if m:
                    label, value = m.group(1).strip(), m.group(2).strip()
                    self.line_fields.append((label, value, node.id))
                    self._by_label.setdefault(label.lower(), (value, node.id))

    def by_synonyms(self, synonyms: tuple[str, ...]) -> tuple[str, str] | None:
        # Exact label match first (most reliable).
        for syn in synonyms:
            hit = self._by_label.get(syn.lower())
            if hit:
                return hit
        # Looser contains-match, but only for specific (len>=5) synonyms so short tokens like
        # "tax"/"date"/"total" don't bleed across fields (e.g. "total" matching "subtotal").
        for label, (value, node_id) in self._by_label.items():
            for syn in synonyms:
                s = syn.lower()
                if len(s) >= 5 and s in label:
                    return value, node_id
        return None

    def entities(self, etype: str) -> list[tuple[str, str]]:
        return [(e.value, e.node_id) for e in self.extraction.entities if e.type == etype]

    def field(
        self, name: str, label: str, synonyms: tuple[str, ...], *, required: bool = False
    ) -> ExtractedField:
        hit = self.by_synonyms(synonyms)
        if hit:
            value, node_id = hit
            return ExtractedField(
                name=name,
                label=label,
                value=value,
                confidence=0.9,
                node_id=node_id,
                status="found",
            )
        return ExtractedField(name=name, label=label, value=None, confidence=0.0, status="missing")


class DocumentSkill(ABC):
    """One document purpose. Subclasses are deterministic and offline."""

    label: str = "document"
    title: str = "Document"
    category: str = "business"
    required_fields: set[str] = set()

    @abstractmethod
    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]: ...

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        return []

    @abstractmethod
    def recommend(
        self,
        doc: CanonicalDocument,
        fields: list[ExtractedField],
        findings: list[SkillFinding],
    ) -> list[RecommendedAction]: ...
