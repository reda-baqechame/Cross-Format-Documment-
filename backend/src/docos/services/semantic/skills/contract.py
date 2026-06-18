"""Contract skill — surfaces the clauses and dates that matter, and the risks a reviewer hunts."""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import (
    DocumentSkill,
    ExtractedField,
    FieldFinder,
    RecommendedAction,
    SkillFinding,
    document_text,
)
from docos.services.semantic.skills.generic import pii_warning

_SYNONYMS: dict[tuple[str, str], tuple[str, ...]] = {
    ("parties", "Parties"): ("between", "parties", "by and between"),
    ("effective_date", "Effective date"): ("effective date", "dated", "commencement date"),
    ("term", "Term"): ("term", "duration"),
    ("governing_law", "Governing law"): ("governing law", "jurisdiction", "governed by"),
    ("termination_notice", "Termination notice"): ("termination", "notice period", "terminate"),
}


class ContractSkill(DocumentSkill):
    label = "contract"
    title = "Contract"
    category = "legal"
    required_fields = {"parties", "governing_law"}

    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]:
        finder = FieldFinder(doc)
        return [finder.field(name, label, syns) for (name, label), syns in _SYNONYMS.items()]

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        findings: list[SkillFinding] = []
        text = document_text(doc)
        by_name = {f.name: f for f in fields}

        if "automatically renew" in text or "auto-renew" in text or "auto renew" in text:
            findings.append(
                SkillFinding(
                    level="warn",
                    code="contract.auto_renewal",
                    message="Auto-renewal clause detected — review the cancellation window.",
                )
            )
        if "unlimited" in text and ("liability" in text or "indemnif" in text):
            findings.append(
                SkillFinding(
                    level="warn",
                    code="contract.unlimited_liability",
                    message="Possible unlimited liability / indemnification language.",
                )
            )
        if by_name["governing_law"].status == "missing":
            findings.append(
                SkillFinding(
                    level="warn",
                    code="missing.governing_law",
                    message="No governing-law clause found.",
                )
            )
        warning = pii_warning(doc)
        if warning:
            findings.append(warning)
        return findings

    def recommend(
        self,
        doc: CanonicalDocument,
        fields: list[ExtractedField],
        findings: list[SkillFinding],
    ) -> list[RecommendedAction]:
        actions = [
            RecommendedAction(
                id="export_docx", label="Export to Word", kind="export", params={"format": "docx"}
            )
        ]
        if any(f.code == "pii.present" for f in findings):
            actions.append(
                RecommendedAction(id="redact", label="Redact personal info", kind="redact")
            )
        actions.append(RecommendedAction(id="seal", label="Add integrity seal", kind="sign"))
        return actions
