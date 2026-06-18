"""Skill selection — classify the document's purpose, then pick a deep skill or the generic one."""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import DocumentSkill, document_text
from docos.services.semantic.skills.contract import ContractSkill
from docos.services.semantic.skills.generic import GenericSkill
from docos.services.semantic.skills.invoice import InvoiceSkill
from docos.services.semantic.skills.resume import ResumeSkill
from docos.services.semantic.skills.taxonomy import DocType, classify_purpose

# Deep skills and the taxonomy purpose ids they claim.
_DEEP: list[tuple[DocumentSkill, set[str]]] = [
    (InvoiceSkill(), {"invoice", "commercial_invoice", "receipt"}),
    (ContractSkill(), {"contract", "nda", "employment_agreement", "lease", "terms_of_service"}),
    (ResumeSkill(), {"resume"}),
]


def select_skill(
    doc: CanonicalDocument,
) -> tuple[DocumentSkill, DocType | None, float, list[str]]:
    """Return (skill, detected DocType|None, confidence, signals). Never returns no skill."""
    dt, confidence, signals = classify_purpose(document_text(doc))
    if dt is not None:
        for skill, claimed in _DEEP:
            if dt.id in claimed:
                return skill, dt, confidence, signals
        return GenericSkill(dt.id, dt.label, dt.category), dt, confidence, signals
    return GenericSkill("document", "Document", "business"), None, 0.0, []
