"""Configurable deep skills for the remaining high-demand document classes."""

from __future__ import annotations

from dataclasses import dataclass

from docos.model.document import CanonicalDocument
from docos.services.semantic.skills import (
    DocumentSkill,
    ExtractedField,
    FieldFinder,
    RecommendedAction,
    SkillFinding,
    document_text,
)
from docos.services.semantic.skills.generic import pii_warning, universal_actions


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    synonyms: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class SkillProfile:
    fields: tuple[FieldSpec, ...]
    concepts: tuple[tuple[str, str, tuple[str, ...]], ...]
    export_format: str = "docx"


HIGH_DEMAND_IDS = {
    "proposal",
    "sow",
    "business_plan",
    "report",
    "sop",
    "marketing_plan",
    "press_release",
    "white_paper",
    "budget",
    "balance_sheet",
    "income_statement",
    "privacy_policy",
    "api_doc",
    "prd",
    "srs",
    "user_manual",
    "research_paper",
    "thesis",
    "bill_of_lading",
    "packing_list",
    "certificate_of_origin",
    "customs_declaration",
    "air_waybill",
    "purchase_agreement",
    "inspection_report",
    "appraisal",
}


_DEFAULT_PROFILE = SkillProfile(
    fields=(
        FieldSpec("owner", "Owner", ("owner", "prepared by", "author")),
        FieldSpec("date", "Date", ("date", "issued", "effective date")),
    ),
    concepts=(
        ("summary", "Executive summary / overview", ("summary", "overview", "objective")),
        ("next_steps", "Next steps", ("next steps", "action items", "recommendation")),
    ),
)

_PROFILES: dict[str, SkillProfile] = {
    "proposal": SkillProfile(
        fields=(
            FieldSpec("client", "Client", ("client", "customer", "prepared for"), True),
            FieldSpec("scope", "Scope", ("scope", "scope of work"), True),
            FieldSpec("price", "Price", ("price", "fee", "investment", "total"), True),
        ),
        concepts=(
            ("problem", "Problem / need", ("problem", "need", "challenge")),
            ("deliverables", "Deliverables", ("deliverables", "what we will deliver")),
            ("timeline", "Timeline", ("timeline", "schedule", "milestone")),
            ("acceptance", "Acceptance criteria", ("acceptance criteria", "approval")),
        ),
    ),
    "sow": SkillProfile(
        fields=(
            FieldSpec("client", "Client", ("client", "customer", "prepared for"), True),
            FieldSpec("deliverables", "Deliverables", ("deliverables",), True),
            FieldSpec("timeline", "Timeline", ("timeline", "milestones"), True),
        ),
        concepts=(
            ("scope", "Scope", ("scope", "in scope")),
            ("deliverables", "Deliverables", ("deliverables", "delivery")),
            ("out_of_scope", "Out of scope", ("out of scope", "exclusions")),
            ("acceptance", "Acceptance criteria", ("acceptance criteria", "sign-off")),
        ),
    ),
    "report": SkillProfile(
        fields=(FieldSpec("prepared_by", "Prepared by", ("prepared by", "author")),),
        concepts=(
            ("summary", "Executive summary", ("executive summary", "summary")),
            ("findings", "Findings", ("findings", "results")),
            ("recommendations", "Recommendations", ("recommendations", "next steps")),
            ("methodology", "Methodology", ("methodology", "approach")),
        ),
    ),
    "sop": SkillProfile(
        fields=(FieldSpec("owner", "Process owner", ("owner", "process owner"), True),),
        concepts=(
            ("purpose", "Purpose", ("purpose",)),
            ("scope", "Scope", ("scope",)),
            ("procedure", "Procedure", ("procedure", "steps")),
            ("roles", "Roles", ("roles", "responsibilities")),
            ("revision", "Revision control", ("revision", "version", "last updated")),
        ),
    ),
    "budget": SkillProfile(
        fields=(
            FieldSpec("period", "Period", ("period", "fiscal year", "month"), True),
            FieldSpec("total", "Total", ("total", "budget total"), True),
        ),
        concepts=(
            ("revenue", "Revenue / income", ("revenue", "income")),
            ("expense", "Expenses", ("expense", "cost")),
            ("variance", "Variance", ("variance", "actual vs budget")),
        ),
        export_format="xlsx",
    ),
    "balance_sheet": SkillProfile(
        fields=(FieldSpec("period", "Period", ("period", "as of"), True),),
        concepts=(
            ("assets", "Assets", ("assets",)),
            ("liabilities", "Liabilities", ("liabilities",)),
            ("equity", "Equity", ("equity",)),
        ),
        export_format="xlsx",
    ),
    "income_statement": SkillProfile(
        fields=(FieldSpec("period", "Period", ("period", "for the year", "for the month"), True),),
        concepts=(
            ("revenue", "Revenue", ("revenue", "sales")),
            ("expenses", "Expenses", ("expenses", "cost of goods")),
            ("net_income", "Net income", ("net income", "profit", "loss")),
        ),
        export_format="xlsx",
    ),
    "privacy_policy": SkillProfile(
        fields=(FieldSpec("effective_date", "Effective date", ("effective date", "last updated")),),
        concepts=(
            ("data_collected", "Data collected", ("we collect", "personal data")),
            ("use", "How data is used", ("use your", "we use")),
            ("sharing", "Sharing / processors", ("share", "third party", "processor")),
            ("rights", "User rights", ("rights", "access", "delete", "opt out")),
        ),
    ),
    "api_doc": SkillProfile(
        fields=(FieldSpec("base_url", "Base URL", ("base url", "endpoint")),),
        concepts=(
            ("auth", "Authentication", ("authentication", "api key", "bearer")),
            ("request", "Request shape", ("request", "parameters")),
            ("response", "Response shape", ("response", "status code")),
            ("errors", "Errors", ("error", "failure", "rate limit")),
        ),
    ),
    "research_paper": SkillProfile(
        fields=(FieldSpec("authors", "Authors", ("authors", "by")),),
        concepts=(
            ("abstract", "Abstract", ("abstract",)),
            ("methodology", "Methodology", ("methodology", "methods")),
            ("results", "Results", ("results", "findings")),
            ("references", "References", ("references", "bibliography")),
        ),
    ),
    "bill_of_lading": SkillProfile(
        fields=(
            FieldSpec("shipper", "Shipper", ("shipper",), True),
            FieldSpec("consignee", "Consignee", ("consignee",), True),
            FieldSpec("carrier", "Carrier", ("carrier",), True),
        ),
        concepts=(
            ("goods", "Goods description", ("description of goods", "goods")),
            ("ports", "Ports / route", ("port of loading", "port of discharge")),
            ("weight", "Weight", ("weight", "gross", "net")),
        ),
        export_format="xlsx",
    ),
    "purchase_agreement": SkillProfile(
        fields=(
            FieldSpec("buyer", "Buyer", ("buyer",), True),
            FieldSpec("seller", "Seller", ("seller",), True),
            FieldSpec("price", "Purchase price", ("purchase price", "price"), True),
        ),
        concepts=(
            ("property", "Property", ("property", "address", "legal description")),
            ("closing", "Closing", ("closing", "completion date")),
            ("conditions", "Conditions", ("condition", "contingency")),
        ),
    ),
}


class HighDemandSkill(DocumentSkill):
    def __init__(self, type_id: str, title: str, category: str) -> None:
        self.label = type_id
        self.title = title
        self.category = category
        profile = _PROFILES.get(type_id, _DEFAULT_PROFILE)
        self.required_fields = {f.name for f in profile.fields if f.required}

    @property
    def profile(self) -> SkillProfile:
        return _PROFILES.get(self.label, _DEFAULT_PROFILE)

    def extract(self, doc: CanonicalDocument) -> list[ExtractedField]:
        finder = FieldFinder(doc)
        return [
            finder.field(spec.name, spec.label, spec.synonyms, required=spec.required)
            for spec in self.profile.fields
        ]

    def check(self, doc: CanonicalDocument, fields: list[ExtractedField]) -> list[SkillFinding]:
        text = document_text(doc)
        findings: list[SkillFinding] = []
        for field in fields:
            if field.name in self.required_fields and field.status == "missing":
                findings.append(
                    SkillFinding(
                        level="warn",
                        code=f"missing.{field.name}",
                        message=f"{field.label} was not found.",
                    )
                )
        for code, label, keywords in self.profile.concepts:
            if any(k in text for k in keywords):
                findings.append(
                    SkillFinding(level="pass", code=f"{code}.present", message=f"{label} found.")
                )
            else:
                findings.append(
                    SkillFinding(
                        level="warn",
                        code=f"missing.{code}",
                        message=f"{label} is missing or unclear.",
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
        has_pii = any(f.code == "pii.present" for f in findings)
        actions = universal_actions(doc, has_pii)
        preferred = self.profile.export_format
        if preferred != "docx":
            actions.insert(
                0,
                RecommendedAction(
                    id=f"export_{preferred}",
                    label=f"Export to {preferred.upper()}",
                    kind="export",
                    params={"format": preferred},
                ),
            )
        return actions
