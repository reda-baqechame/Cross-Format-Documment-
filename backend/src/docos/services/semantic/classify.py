"""Document classification — a lightweight, deterministic document-type detector.

Keyword-signal scoring over the canonical model's text. Offline and explainable (it
returns the signals that fired), it covers the common business document types; an LLM
classifier can be layered on later for finer categories.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted

# category -> signal keywords (lowercased, substring match on the document text)
_SIGNALS: dict[str, tuple[str, ...]] = {
    "invoice": ("invoice", "amount due", "total due", "subtotal", "bill to", "due date"),
    "receipt": ("receipt", "thank you for your", "cashier", "change due", "card ending"),
    "contract": ("agreement", "hereby", "the parties", "shall", "terms and conditions", "whereas"),
    "resume": ("experience", "education", "skills", "curriculum vitae", "résumé", "resume"),
    "letter": ("dear ", "sincerely", "best regards", "yours truly"),
    "report": ("introduction", "summary", "conclusion", "methodology", "findings"),
    "form": ("please fill", "signature", "date of birth", "checkbox", "applicant"),
    "presentation": ("agenda", "next steps", "thank you", "slide", "q&a", "our mission"),
}


class Classification(BaseModel):
    label: str
    confidence: float
    signals: list[str]


def _document_text(doc: CanonicalDocument) -> str:
    parts = [
        getattr(n, "text", "")
        for n in doc.walk()
        if getattr(n, "text", "") and not is_redacted(doc, n.id)
    ]
    return "\n".join(parts).lower()


def classify(doc: CanonicalDocument) -> Classification:
    text = _document_text(doc)
    scores: dict[str, list[str]] = {}
    for label, keywords in _SIGNALS.items():
        hits = [k for k in keywords if k in text]
        if hits:
            scores[label] = hits

    if not scores:
        return Classification(label="other", confidence=0.0, signals=[])

    best = max(scores, key=lambda k: len(scores[k]))
    matched = scores[best]
    confidence = round(len(matched) / len(_SIGNALS[best]), 2)
    return Classification(label=best, confidence=confidence, signals=matched)
