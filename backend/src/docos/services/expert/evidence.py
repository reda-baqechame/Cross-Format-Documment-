"""Evidence binding — turn canonical-model nodes into cited ``EvidenceRef`` objects.

The reason generic document tools hallucinate is they let the model assert a fact without
showing where it came from. This module is the opposite: every value we extract is
returned together with the exact node id, page number, and verbatim source text it was
read from, so a finding can never point to thin air.

It walks the canonical model the same way ``semantic.extract._text_nodes`` does, but keeps
the page number (resolved by walking up to the enclosing ``page`` node) and the raw span
that matched, so downstream rules cite the precise location a human would open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from docos.model.document import CanonicalDocument
from docos.services.semantic.extract import is_redacted


@dataclass(frozen=True)
class SourcedSpan:
    """A text match plus enough provenance to build an EvidenceRef."""

    node_id: str
    page_number: int | None
    raw_text: str
    bbox: tuple[float, float, float, float] | None = None


def _page_number_for(doc: CanonicalDocument, node_id: str) -> int | None:
    """Walk up the parent chain to the enclosing page node and read its page_number."""
    node = doc.nodes.get(node_id)
    if node is None:
        return None
    current = node
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        if getattr(current, "type", None) == "page":
            return getattr(current, "page_number", None)
        parent_id = getattr(current, "parent_id", None)
        current = doc.nodes.get(parent_id) if parent_id else None
    return None


def _bbox_of(doc: CanonicalDocument, node_id: str) -> tuple[float, float, float, float] | None:
    node = doc.nodes.get(node_id)
    bbox = getattr(node, "bbox", None) if node else None
    if bbox is None:
        return None
    try:
        return (float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1))
    except AttributeError:
        # BBox may be a tuple/dataclass; tolerate either.
        try:
            return tuple(float(v) for v in bbox)  # type: ignore[union-attr]
        except Exception:
            return None


def sourced_spans(doc: CanonicalDocument) -> list[SourcedSpan]:
    """All non-redacted text spans in reading order, each with page + bbox provenance."""
    out: list[SourcedSpan] = []
    for node in doc.walk():
        text = (getattr(node, "text", "") or "").strip()
        if text and not is_redacted(doc, node.id):
            out.append(
                SourcedSpan(
                    node_id=node.id,
                    page_number=_page_number_for(doc, node.id),
                    raw_text=text,
                    bbox=_bbox_of(doc, node.id),
                )
            )
    return out


@dataclass(frozen=True)
class Match:
    """A regex hit bound to its source span."""

    span: SourcedSpan
    value: str
    full_match_text: str


def find(pattern: re.Pattern[str], doc: CanonicalDocument, *, group: int = 1) -> list[Match]:
    """All matches of ``pattern`` across the document, each cited to its span."""
    matches: list[Match] = []
    for span in sourced_spans(doc):
        for m in pattern.finditer(span.raw_text):
            try:
                value = m.group(group)
            except IndexError:
                value = m.group(0)
            matches.append(Match(span=span, value=value, full_match_text=m.group(0)))
    return matches


def first(pattern: re.Pattern[str], doc: CanonicalDocument, *, group: int = 1) -> Match | None:
    """The first match of ``pattern`` in reading order, or None."""
    return next(iter(find(pattern, doc, group=group)), None)


def evidence_ref(
    *,
    document_id: str,
    document_type: str | None,
    field_name: str | None,
    match: Match,
    normalized_value: str | None = None,
) -> EvidenceRef:  # noqa: F821 — forward ref resolved at call time
    """Build an EvidenceRef from a Match. Imported lazily to avoid a circular import."""
    from docos.services.expert.schemas import EvidenceRef

    return EvidenceRef(
        document_id=document_id,
        document_type=document_type,
        page_number=match.span.page_number,
        node_id=match.span.node_id,
        field_name=field_name,
        raw_text=match.span.raw_text,
        normalized_value=normalized_value if normalized_value is not None else match.value,
        bbox=match.span.bbox,
    )
