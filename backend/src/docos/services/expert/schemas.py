"""Pydantic schemas for the expert DocumentOps spine.

These are the typed objects every vertical pack and every packet-audit route speaks.
The two load-bearing contracts:

  * ``ExpertFinding`` — one evidence-bound expert conclusion (a contradiction, a missing
    document, a compliance risk, a redaction leak). It never just says "risk found"; it
    cites where the fact came from, how confident we are, what the business impact is, and
    what to do about it.

  * ``ExpertReport`` — the full decision artifact a buyer receives: verdict + readiness
    score + documents + missing documents + extracted fields + findings + recommended
    actions + redaction/export/audit summaries.

Why a separate vocabulary from ``packs/*.PacketFinding``: the legacy pack findings carry
``severity/code/message`` only — no evidence, no impact, no action, no confidence. Those
packs keep working unchanged; this is the superset they are adapted to emit (see
``expert/adapters.py``).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Enums ──────────────────────────────────────────────────────────────────────

FindingType = Literal[
    "missing_document",
    "field_mismatch",
    "calculation_error",
    "compliance_risk",
    "redaction_risk",
    "metadata_risk",
    "signature_missing",
    "date_problem",
    "party_mismatch",
    "currency_mismatch",
    "quantity_mismatch",
    "weight_mismatch",
    "hs_code_risk",
    "export_validation_error",
    "completeness_gap",
    "coverage_problem",
    "other",
]

FindingSeverity = Literal["info", "warning", "blocking"]

Verdict = Literal["ready", "needs_review", "blocked"]

DetectionMethod = Literal["deterministic_rule", "llm_assisted", "hybrid"]


# ── Evidence ───────────────────────────────────────────────────────────────────


class EvidenceRef(BaseModel):
    """A single citation backing one factual claim.

    Every ExpertFinding MUST carry at least one EvidenceRef whose ``raw_text`` is the
    verbatim source span. A finding with no evidence is illegal in this layer — the rule
    must instead set ``human_review_required`` and explain why the signal is ambiguous.
    """

    document_id: str
    document_type: str | None = None
    page_number: int | None = None
    node_id: str | None = None
    field_name: str | None = None
    raw_text: str
    normalized_value: str | None = None
    bbox: tuple[float, float, float, float] | None = None


# ── Findings ───────────────────────────────────────────────────────────────────


class ExpertFinding(BaseModel):
    """One evidence-bound expert conclusion."""

    id: str
    type: FindingType
    severity: FindingSeverity
    title: str
    explanation: str
    business_impact: str | None = None
    recommended_action: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    detection_method: DetectionMethod = "deterministic_rule"
    human_review_required: bool = False
    fix_available: bool = False
    rule_code: str | None = None  # e.g. "invoice_total_vs_po_total"


class RecommendedAction(BaseModel):
    """A user-facing next step derived from one or more findings."""

    title: str
    detail: str
    severity: FindingSeverity
    related_findings: list[str] = Field(default_factory=list)  # finding ids
    auto_fixable: bool = False


# ── Extracted facts ────────────────────────────────────────────────────────────


class ExtractedField(BaseModel):
    """A single normalized business fact bound to its source evidence."""

    name: str  # e.g. "commercial_invoice.total_amount"
    value: str
    document_id: str
    document_type: str | None = None
    evidence: EvidenceRef
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ── Packet structure ───────────────────────────────────────────────────────────


class DocumentSummary(BaseModel):
    document_id: str
    title: str | None = None
    document_type: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MissingDocument(BaseModel):
    document_type: str
    label: str
    severity: FindingSeverity
    why_required: str


class RedactionSummary(BaseModel):
    sensitive_findings: int = 0
    redacted_nodes: int = 0
    metadata_sanitized: bool = False
    recoverable_secret_bytes: int = 0  # must be 0 for a send-ready packet
    notes: str | None = None


class ExportSummary(BaseModel):
    formats_produced: list[str] = Field(default_factory=list)
    validation_passed: bool = False
    validation_findings_count: int = 0
    notes: str | None = None


class AuditSummary(BaseModel):
    actions: int = 0
    patches_applied: int = 0
    reversible: bool = True  # all fixes go through ReversiblePatch
    notes: str | None = None


# ── Unified job result (Phase 1 Command Center) ───────────────────────────────


JobType = Literal["clean_before_send", "packet_audit", "patch_apply", "export"]


class ResultContract(BaseModel):
    """One artifact shape for every serious document job — readiness or packet audit."""

    job_type: JobType
    verdict: Verdict
    score: int = Field(ge=0, le=100)
    findings: list[ExpertFinding] = Field(default_factory=list)
    fix_plans_available: int = 0
    clean_export_available: bool = False
    proof_report_url: str | None = None
    human_review_required: bool = False


# ── The decision artifact ──────────────────────────────────────────────────────


class ExpertReport(BaseModel):
    """The full expert artifact a buyer receives for one packet.

    ``verdict`` is the single most important field and is derived deterministically:
      blocked       — ≥1 blocking finding
      needs_review  — no blocking finding but ≥1 warning OR any human_review_required
      ready         — no blocking, no warning, no human review pending
    """

    packet_id: str
    pack: str  # which vertical produced this, e.g. "import_export"
    verdict: Verdict
    readiness_score: float = Field(ge=0.0, le=1.0)
    executive_summary: str
    documents_detected: list[DocumentSummary] = Field(default_factory=list)
    missing_documents: list[MissingDocument] = Field(default_factory=list)
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    findings: list[ExpertFinding] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    redaction_summary: RedactionSummary = Field(default_factory=RedactionSummary)
    export_summary: ExportSummary = Field(default_factory=ExportSummary)
    audit_summary: AuditSummary = Field(default_factory=AuditSummary)
    model_versions: dict[str, str] = Field(default_factory=dict)
    generated_at: str  # ISO-8601 UTC
