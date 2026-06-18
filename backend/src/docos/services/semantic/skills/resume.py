"""Résumé skill — pulls contact + profile facts and flags missing contact details."""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import (
    DocumentSkill,
    ExtractedField,
    FieldFinder,
    RecommendedAction,
    SkillFinding,
)
from docos.services.semantic.skills.generic import pii_warning


class ResumeSkill(DocumentSkill):
    label = "resume"
    title = "Résumé"
    category = "hr"
    required_fields = {"email"}

    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]:
        finder = FieldFinder(doc)
        fields: list[ExtractedField] = []

        def from_entity(name: str, label: str, etype: str) -> ExtractedField:
            ents = finder.entities(etype)
            if ents:
                value, node_id = ents[0]
                return ExtractedField(
                    name=name,
                    label=label,
                    value=value,
                    confidence=0.8,
                    node_id=node_id,
                    status="found",
                )
            return ExtractedField(name=name, label=label, value=None, status="missing")

        fields.append(from_entity("email", "Email", "email"))
        fields.append(from_entity("phone", "Phone", "phone"))
        fields.append(finder.field("education", "Education", ("education", "degree", "university")))
        fields.append(finder.field("skills", "Skills", ("skills", "technical skills")))
        return fields

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        findings: list[SkillFinding] = []
        by_name = {f.name: f for f in fields}
        if by_name["email"].status == "missing" and by_name["phone"].status == "missing":
            findings.append(
                SkillFinding(
                    level="warn",
                    code="missing.contact",
                    message="No email or phone contact detail found.",
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
        return actions
