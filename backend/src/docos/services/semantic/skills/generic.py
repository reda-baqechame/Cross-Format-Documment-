"""Generic skill — the fallback for any recognized purpose without a deep skill yet.

Guarantees every document produces a useful Autopilot result: category + type, universal key
facts (entities + Label:value fields), a PII warning, and universal next actions. Deep skills
take over for the high-value purposes; everything else lands here.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.provenance import sensitive
from docos.services.semantic.skills import (
    DocumentSkill,
    ExtractedField,
    FieldFinder,
    RecommendedAction,
    SkillFinding,
)


def pii_warning(doc: CanonicalDocument) -> SkillFinding | None:
    findings = sensitive.scan_document(doc)
    if not findings:
        return None
    return SkillFinding(
        level="warn",
        code="pii.present",
        message=f"{len(findings)} possible personal/sensitive item(s) detected.",
    )


def universal_actions(doc: CanonicalDocument, has_pii: bool) -> list[RecommendedAction]:
    actions: list[RecommendedAction] = [
        RecommendedAction(
            id="export_docx",
            label="Export to Word",
            kind="export",
            params={"format": "docx"},
        )
    ]
    if doc.meta.source_format == "pdf":
        actions.append(
            RecommendedAction(
                id="export_pdf", label="Export to PDF", kind="export", params={"format": "pdf"}
            )
        )
    if has_pii:
        actions.append(RecommendedAction(id="redact", label="Redact personal info", kind="redact"))
    actions.append(RecommendedAction(id="seal", label="Add integrity seal", kind="sign"))
    return actions


class GenericSkill(DocumentSkill):
    def __init__(self, label: str, title: str, category: str) -> None:
        self.label = label
        self.title = title
        self.category = category
        self.required_fields = set()

    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]:
        finder = FieldFinder(doc)
        fields: list[ExtractedField] = []
        for label, value, node_id in finder.line_fields[:6]:
            fields.append(
                ExtractedField(
                    name=label.lower().replace(" ", "_")[:40] or "field",
                    label=label,
                    value=value,
                    confidence=0.7,
                    node_id=node_id,
                    status="found",
                )
            )
        if not fields:  # no labelled fields — surface notable entities instead
            for etype in ("money", "date", "email", "phone"):
                ents = finder.entities(etype)
                if ents:
                    value, node_id = ents[0]
                    fields.append(
                        ExtractedField(
                            name=etype,
                            label=etype.title(),
                            value=value,
                            confidence=0.5,
                            node_id=node_id,
                            status="low_confidence",
                        )
                    )
        return fields

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        warning = pii_warning(doc)
        return [warning] if warning else []

    def recommend(
        self,
        doc: CanonicalDocument,
        fields: list[ExtractedField],
        findings: list[SkillFinding],
    ) -> list[RecommendedAction]:
        has_pii = any(f.code == "pii.present" for f in findings)
        return universal_actions(doc, has_pii)
