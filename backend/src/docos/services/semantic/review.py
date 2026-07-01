"""Human-in-the-loop review queue — surface what a person should check, by confidence.

OCR already tags low-confidence words (``attrs["ocr_review"]``) and typed extraction carries a
per-field confidence, but nothing exposed them — low-confidence values flowed downstream silently.
This collects them into one redaction-aware, confidence-gated queue a reviewer (or an approval
workflow) can work through. Deterministic and offline. Corrections use the existing patch endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.semantic import intelligence

# Default confidence floor (0–100 OCR scale / 0–1 field scale normalised to it). Below this a value
# is queued for human review rather than trusted.
_OCR_FLOOR = 60.0
_FIELD_FLOOR = 0.6


class ReviewItem(BaseModel):
    node_id: str
    kind: str  # ocr | field
    label: str
    value: str
    confidence: float  # 0–100
    source_engine: str | None = None
    reason: str


class ReviewQueue(BaseModel):
    doc_id: str
    ocr_floor: float
    field_floor: float
    items: list[ReviewItem]


def build_review_queue(
    doc: CanonicalDocument, *, ocr_floor: float = _OCR_FLOOR, field_floor: float = _FIELD_FLOOR
) -> ReviewQueue:
    """Collect low-confidence OCR words + low-confidence extracted fields for human review."""
    items: list[ReviewItem] = []

    # 1) Low-confidence OCR words (skip redacted — their text is gone and must never resurface).
    for node in doc.walk():
        if node.type != "run" or is_redacted(doc, node.id):
            continue
        attrs = getattr(node, "attrs", {}) or {}
        if "confidence" not in attrs and not attrs.get("ocr_review"):
            continue  # not an OCR-sourced run
        conf = float(attrs.get("confidence", 0.0))
        if attrs.get("ocr_review") or conf < ocr_floor:
            items.append(
                ReviewItem(
                    node_id=node.id,
                    kind="ocr",
                    label="Low-confidence OCR text",
                    value=getattr(node, "text", "") or "",
                    confidence=round(conf, 1),
                    source_engine=attrs.get("source_engine"),
                    reason=f"OCR confidence {conf:.0f} is below the {ocr_floor:.0f} review floor.",
                )
            )

    # 2) Low-confidence / missing typed fields from document intelligence.
    insight = intelligence.analyze(doc)
    for field in insight.fields:
        if field.node_id is not None and is_redacted(doc, field.node_id):
            continue
        if field.confidence < field_floor:
            items.append(
                ReviewItem(
                    node_id=field.node_id or "",
                    kind="field",
                    label=field.key,
                    value=field.value,
                    confidence=round(field.confidence * 100, 1),
                    reason=(
                        f"Extracted '{field.key}' has low confidence "
                        f"({field.confidence:.2f} < {field_floor:.2f})."
                    ),
                )
            )

    return ReviewQueue(doc_id=doc.doc_id, ocr_floor=ocr_floor, field_floor=field_floor, items=items)
