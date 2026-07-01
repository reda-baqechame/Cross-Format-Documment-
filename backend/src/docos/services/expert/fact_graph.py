"""Normalized business fact graph.

Extraction returns raw strings ("CAD 14,920.00", "1,240 KGS", "2026-06-30"). Comparison
needs typed values (1240.0 kg, currency CAD, money 14920.0). This module normalizes every
extracted field into a typed ``Fact`` keyed by a stable business name so a rule can ask
"do the invoice total and the PO total agree?" without caring which document each came
from or how the number was formatted.

This is what lets one vertical's rules reuse another vertical's extractions, and what
makes cross-document contradiction detection a graph operation rather than string fiddling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from docos.services.expert.schemas import EvidenceRef, ExtractedField

FactKind = Literal[
    "money",
    "weight",
    "quantity",
    "date",
    "text",
    "currency",
    "code",
]

# A "role" scopes a fact to where it lives in a packet, e.g. ("commercial_invoice", "total_amount")
# or ("purchase_order", "total_amount"). Rules compare facts that share the field tail across roles.
RoleKey = tuple[str, str]  # (document_type_or_role, field_name)


@dataclass(frozen=True)
class Fact:
    """A typed, normalized, cited business fact."""

    role: str  # document type / role, e.g. "commercial_invoice"
    field: str  # business field name, e.g. "total_amount"
    value: float | str
    unit: str | None  # currency code, "kg", "lb", "each", etc.
    confidence: float
    field_ref: ExtractedField  # the cited source

    @property
    def key(self) -> RoleKey:
        return (self.role, self.field)

    @property
    def field_tail(self) -> str:
        return self.field


@dataclass
class FactGraph:
    """All facts extracted from a packet, queryable by role/field."""

    facts: list[Fact] = field(default_factory=list)

    def add(self, fact: Fact) -> None:
        self.facts.append(fact)

    def by_field(self, field_name: str) -> list[Fact]:
        """All facts for a given business field across all roles."""
        return [f for f in self.facts if f.field == field_name]

    def by_role(self, role: str) -> list[Fact]:
        return [f for f in self.facts if f.role == role]

    def one(self, role: str, field_name: str) -> Fact | None:
        for f in self.facts:
            if f.role == role and f.field == field_name:
                return f
        return None

    def values_for_field(self, field_name: str) -> list[Fact]:
        return self.by_field(field_name)


# ── Normalizers ────────────────────────────────────────────────────────────────

_CURRENCY_TOKEN = re.compile(r"\b(USD|EUR|GBP|CNY|JPY|CAD|AUD|CHF|HKD|MAD|AED)\b")
_NUMBER = re.compile(r"-?[\d][\d,]*\.?\d{0,2}")
_WEIGHT_UNIT = re.compile(r"\b(kgs?|lbs?|kilograms?|pounds?|kg|lb)\b", re.I)
_INCOTERMS = re.compile(r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b")


def parse_money(raw: str) -> tuple[float | None, str | None]:
    """Return (amount, currency) or (None, None) if not parseable."""
    cur = _CURRENCY_TOKEN.search(raw)
    m = _NUMBER.search(raw.replace(",", ""))
    if not m:
        return None, None
    try:
        return float(m.group(0)), cur.group(1) if cur else None
    except ValueError:
        return None, None


def parse_weight(raw: str) -> tuple[float | None, str | None]:
    """Return (value, normalized_unit) where unit is 'kg' or 'lb', or (None, None)."""
    m = _NUMBER.search(raw.replace(",", ""))
    if not m:
        return None, None
    u = _WEIGHT_UNIT.search(raw)
    unit_norm = None
    if u:
        lo = u.group(1).lower()
        unit_norm = "lb" if lo.startswith("lb") or lo.startswith("pound") else "kg"
    try:
        return float(m.group(0)), unit_norm
    except ValueError:
        return None, None


def parse_incoterms(raw: str) -> str | None:
    m = _INCOTERMS.search(raw.upper())
    return m.group(1) if m else None


# ── Builders ───────────────────────────────────────────────────────────────────


def money_fact(
    *,
    role: str,
    field_name: str,
    raw: str,
    document_id: str,
    document_type: str | None,
    node_id: str | None,
    page_number: int | None,
    raw_text: str,
    bbox: tuple[float, float, float, float] | None = None,
    confidence: float = 1.0,
) -> Fact | None:
    """Build a typed money fact from a raw string, with full citation."""
    amount, currency = parse_money(raw)
    if amount is None:
        return None
    display = f"{currency or ''} {amount:,.2f}".strip()
    ref = _build_ref(
        document_id=document_id,
        document_type=document_type,
        field_name=field_name,
        node_id=node_id,
        page_number=page_number,
        raw_text=raw_text,
        normalized_value=display,
        bbox=bbox,
    )
    return Fact(
        role=role,
        field=field_name,
        value=amount,
        unit=currency,
        confidence=confidence,
        field_ref=ref,
    )


def weight_fact(
    *,
    role: str,
    field_name: str,
    raw: str,
    document_id: str,
    document_type: str | None,
    node_id: str | None,
    page_number: int | None,
    raw_text: str,
    bbox: tuple[float, float, float, float] | None = None,
    confidence: float = 1.0,
) -> Fact | None:
    value, unit = parse_weight(raw)
    if value is None:
        return None
    ref = _build_ref(
        document_id=document_id,
        document_type=document_type,
        field_name=field_name,
        node_id=node_id,
        page_number=page_number,
        raw_text=raw_text,
        normalized_value=f"{value:,.2f} {unit or 'kg'}",
        bbox=bbox,
    )
    return Fact(
        role=role,
        field=field_name,
        value=value,
        unit=unit or "kg",
        confidence=confidence,
        field_ref=ref,
    )


def text_fact(
    *,
    role: str,
    field_name: str,
    value: str,
    document_id: str,
    document_type: str | None,
    node_id: str | None,
    page_number: int | None,
    raw_text: str,
    bbox: tuple[float, float, float, float] | None = None,
    confidence: float = 1.0,
) -> Fact:
    ref = _build_ref(
        document_id=document_id,
        document_type=document_type,
        field_name=field_name,
        node_id=node_id,
        page_number=page_number,
        raw_text=raw_text,
        normalized_value=value,
        bbox=bbox,
    )
    return Fact(
        role=role,
        field=field_name,
        value=value,
        unit=None,
        confidence=confidence,
        field_ref=ref,
    )


def _build_ref(
    *,
    document_id: str,
    document_type: str | None,
    field_name: str | None,
    node_id: str | None,
    page_number: int | None,
    raw_text: str,
    normalized_value: str | None,
    bbox: tuple[float, float, float, float] | None,
) -> ExtractedField:
    ref = EvidenceRef(
        document_id=document_id,
        document_type=document_type,
        page_number=page_number,
        node_id=node_id,
        field_name=field_name,
        raw_text=raw_text,
        normalized_value=normalized_value,
        bbox=bbox,
    )
    return ExtractedField(
        name=f"{document_type or 'doc'}.{field_name or 'value'}",
        value=normalized_value or raw_text,
        document_id=document_id,
        document_type=document_type,
        evidence=ref,
        confidence=1.0,
    )
