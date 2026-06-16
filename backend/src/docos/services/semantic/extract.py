"""Structured-data extraction (lightweight IDP) over the canonical model.

The deterministic core pulls common entities (dates, money, emails, phones, URLs,
percentages) and "Label: value" fields out of any parsed document — invoices, IDs,
contracts — with node-level provenance. It runs fully offline; a configured LLM can be
layered on later for schema-driven extraction. This is the IDP capability (ABBYY/Textract/
Rossum) expressed once over the shared model instead of per-format pipelines.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted

_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("url", re.compile(r"\bhttps?://[^\s<>()]+", re.IGNORECASE)),
    (
        "money",
        re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d{2})?|\b\d[\d,]*(?:\.\d{2})?\s?(?:USD|EUR|GBP)\b)"),
    ),
    ("percent", re.compile(r"\b\d+(?:\.\d+)?\s?%")),
    (
        "date",
        re.compile(
            r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b"
        ),
    ),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)")),
]

# "Label: value" — a short titled label followed by a concise value on the same line.
_FIELD = re.compile(r"^\s*([A-Z][A-Za-z0-9 /._-]{1,40}?)\s*[:\-]\s*(\S.{0,120}?)\s*$")


class Entity(BaseModel):
    type: str
    value: str
    node_id: str


class Field(BaseModel):
    key: str
    value: str
    node_id: str


class Extraction(BaseModel):
    entities: list[Entity]
    fields: list[Field]


def _text_nodes(doc: CanonicalDocument) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for node in doc.walk():
        text = (getattr(node, "text", "") or "").strip()
        if text and not is_redacted(doc, node.id):
            out.append((node.id, text))
    return out


def extract(doc: CanonicalDocument) -> Extraction:
    entities: list[Entity] = []
    fields: list[Field] = []
    seen_entities: set[tuple[str, str]] = set()

    for node_id, text in _text_nodes(doc):
        for etype, pattern in _ENTITY_PATTERNS:
            for m in pattern.finditer(text):
                value = m.group().strip()
                key = (etype, value)
                if key not in seen_entities:
                    seen_entities.add(key)
                    entities.append(Entity(type=etype, value=value, node_id=node_id))
        fm = _FIELD.match(text)
        if fm:
            fields.append(
                Field(key=fm.group(1).strip(), value=fm.group(2).strip(), node_id=node_id)
            )

    return Extraction(entities=entities, fields=fields)
