"""Request/response DTOs.

These (plus the canonical model) define the OpenAPI schema that ``make codegen``
turns into ``packages/shared-types/src/generated.ts`` — the single source of truth
shared with the frontend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from docos.model.document import CanonicalDocument
from docos.model.patch import PatchOp
from docos.services.provenance.diff import DiffResult
from docos.services.provenance.health import DocumentHealth
from docos.services.provenance.interface import VersionRef
from docos.services.provenance.sensitive import SensitiveFinding
from docos.services.provenance.validation import ValidationReport
from docos.services.semantic.classify import Classification
from docos.services.semantic.extract import Extraction
from docos.services.semantic.intelligence import DocumentInsight
from docos.services.semantic.reader import Citation
from docos.services.semantic.skills.autopilot import AutopilotReport


class HealthCheck(BaseModel):
    status: str
    privacy_mode: str
    blob_backend: str
    db: str
    # AI features (Ask/Summarize/Translate/natural-language edit) are real only when an LLM
    # provider is configured; the UI uses this to show their true state instead of failing silently.
    ai_enabled: bool = False
    llm_provider: str = "noop"
    # Native-editor + storage/db truthing so the UI can show what is actually wired up rather
    # than implying universal native fidelity. ``office_editor`` / ``pdf_editor`` are False until
    # an external provider (OnlyOffice / PDF SDK) is configured; until then editing is structural.
    office_editor: bool = False
    pdf_editor: bool = False
    database: str = "sqlite"


class ReadyCheck(BaseModel):
    """Deep readiness probe — unlike ``/health`` this fails (503) when the app cannot actually
    serve document operations: required tables missing, blob storage unwritable, or migrations
    not applied. Railway points its healthcheck here so a broken deploy never reports healthy."""

    ok: bool
    checks: dict[str, str]


class UploadResponse(BaseModel):
    doc_id: str
    version_id: str
    detected_format: str | None


class DocumentModelResponse(BaseModel):
    document: CanonicalDocument
    version_id: str | None


class DocumentHealthResponse(BaseModel):
    doc_id: str
    health: DocumentHealth


class ValidationReportResponse(BaseModel):
    doc_id: str
    validation: ValidationReport


class AutopilotResponse(BaseModel):
    doc_id: str
    autopilot: AutopilotReport


class HistoryResponse(BaseModel):
    doc_id: str
    versions: list[VersionRef]


class SignRequest(BaseModel):
    signer: str = Field(min_length=1, max_length=200)


class SignatureResponse(BaseModel):
    doc_id: str
    signed: bool
    valid: bool
    signer: str | None
    signed_at: datetime | None


class DocumentSummary(BaseModel):
    doc_id: str
    title: str | None
    source_format: str
    current_version_id: str | None
    created_at: datetime
    tags: list[str] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


class PatchOpDTO(BaseModel):
    """A single explicit, deterministic edit op submitted by the client."""

    op: PatchOp
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class PatchRequest(BaseModel):
    """Either a natural-language ``instruction`` (LLM path) or explicit ``ops``."""

    instruction: str | None = None
    ops: list[PatchOpDTO] | None = None

    @model_validator(mode="after")
    def _require_one(self) -> PatchRequest:
        if not self.instruction and not self.ops:
            raise ValueError("provide either 'instruction' or 'ops'")
        return self


class PatchResponse(BaseModel):
    doc_id: str
    patch_id: str
    applied: bool
    new_version_id: str | None
    intent: str | None


class FindReplaceRequest(BaseModel):
    """Replace every occurrence of ``find`` with ``replace`` across the document."""

    find: str
    replace: str = ""
    match_case: bool = False
    whole_word: bool = False


class FindReplaceResponse(BaseModel):
    """Result of a replace-all: how much changed and the new version it produced."""

    doc_id: str
    applied: bool
    occurrences: int  # total matches replaced
    nodes_changed: int  # distinct run nodes whose text changed
    new_version_id: str | None


class SensitiveScanResponse(BaseModel):
    """Detected PII/secrets and how many distinct nodes a redaction would touch."""

    doc_id: str
    findings: list[SensitiveFinding]
    summary: dict[str, int]  # count per category
    node_count: int  # distinct nodes that would be redacted


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    doc_id: str
    answer: str
    citations: list[Citation]
    used_llm: bool  # False = deterministic offline answer


class SummaryResponse(BaseModel):
    doc_id: str
    summary: str
    citations: list[Citation]
    used_llm: bool


class PagesRequest(BaseModel):
    pages: list[int] = Field(min_length=1)


class RotateRequest(BaseModel):
    # An empty list means "all pages" — the route expands it (matches the UI's "blank = all").
    pages: list[int] = Field(default_factory=list)
    degrees: int = 90


class ReorderRequest(BaseModel):
    order: list[int] = Field(min_length=1)


class MergeRequest(BaseModel):
    doc_ids: list[str] = Field(min_length=1)  # appended after this document, in order


class ProtectRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    owner_password: str | None = Field(default=None, max_length=200)
    allow_print: bool = True


class WatermarkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class DiffResponse(BaseModel):
    doc_id: str
    against: str
    result: DiffResult


class ExtractResponse(BaseModel):
    doc_id: str
    extraction: Extraction


class ClassifyResponse(BaseModel):
    doc_id: str
    classification: Classification


class IntelligenceResponse(BaseModel):
    doc_id: str
    insight: DocumentInsight


class TranslateRequest(BaseModel):
    target_language: str = Field(min_length=2, max_length=40)


class TranslateResponse(BaseModel):
    doc_id: str
    target_language: str
    translated_text: str


class TagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=60)


class TagsResponse(BaseModel):
    doc_id: str
    tags: list[str]


class SearchHit(BaseModel):
    doc_id: str
    title: str | None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class FieldInfo(BaseModel):
    node_id: str
    field_name: str
    field_kind: str
    value: str | None
    required: bool = False
    placeholder: str | None = None
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)
    validation_pattern: str | None = None
    default_value: str | None = None


class FieldsResponse(BaseModel):
    doc_id: str
    fields: list[FieldInfo]


class FillFieldRequest(BaseModel):
    node_id: str
    value: str = Field(max_length=5000)


class CreateFieldRequest(BaseModel):
    field_name: str = Field(min_length=1, max_length=120)
    field_kind: str = Field(default="text", max_length=40)
    parent_id: str | None = None
    index: int | None = Field(default=None, ge=0)
    value: str | None = Field(default=None, max_length=5000)
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=200)
    help_text: str | None = Field(default=None, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=50)
    validation_pattern: str | None = Field(default=None, max_length=300)
    default_value: str | None = Field(default=None, max_length=5000)


class UpdateFieldRequest(BaseModel):
    field_name: str | None = Field(default=None, min_length=1, max_length=120)
    field_kind: str | None = Field(default=None, max_length=40)
    value: str | None = Field(default=None, max_length=5000)
    required: bool | None = None
    placeholder: str | None = Field(default=None, max_length=200)
    help_text: str | None = Field(default=None, max_length=500)
    options: list[str] | None = Field(default=None, max_length=50)
    validation_pattern: str | None = Field(default=None, max_length=300)
    default_value: str | None = Field(default=None, max_length=5000)


class DetectFieldsResponse(BaseModel):
    doc_id: str
    detected: int
    patch: PatchResponse


class AssetUploadResponse(BaseModel):
    doc_id: str
    blob_ref: str
    mime: str
    filename: str | None


class EditorSessionRequest(BaseModel):
    mode: str = Field(default="edit", max_length=40)
    provider: str | None = Field(default=None, max_length=40)


class EditorSessionResponse(BaseModel):
    doc_id: str
    session_id: str
    provider: str
    status: str
    mode: str
    source_format: str
    editor_url: str
    config: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    saved_version_id: str | None = None


class EditorSessionSaveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class EditorSessionSyncRequest(BaseModel):
    client_revision: str | None = Field(default=None, max_length=120)


class OpsAgentPlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    allow_destructive: bool = False


class OpsAgentAction(BaseModel):
    tool: str
    label: str
    destructive: bool = False
    requires_approval: bool = False
    reason: str


class OpsAgentPlanResponse(BaseModel):
    doc_id: str
    goal: str
    classification: str
    actions: list[OpsAgentAction]
    warnings: list[str] = Field(default_factory=list)


WorkflowPreset = Literal[
    "contract_packet",
    "invoice_approval",
    "vendor_onboarding",
    "employee_form_packet",
    "proposal_to_signature",
    "bulk_send_template",
]


class WorkflowPreviewRequest(BaseModel):
    preset: WorkflowPreset


class WorkflowStep(BaseModel):
    id: str
    label: str
    status: str = "pending"
    tool: str
    requires_approval: bool = False
    destructive: bool = False
    reason: str
    result: str | None = None


class WorkflowPreviewResponse(BaseModel):
    doc_id: str
    preset: WorkflowPreset
    classification: str
    steps: list[WorkflowStep]
    warnings: list[str] = Field(default_factory=list)


class WorkflowExecuteRequest(BaseModel):
    preset: WorkflowPreset
    approved_step_ids: list[str] = Field(default_factory=list)
    confirm_destructive: bool = False
    recipients: list[str] = Field(default_factory=list, max_length=100)
    approvers: list[str] = Field(default_factory=list, max_length=50)


class WorkflowExecuteResponse(BaseModel):
    doc_id: str
    preset: WorkflowPreset
    classification: str
    executed_steps: list[WorkflowStep]
    skipped_steps: list[WorkflowStep]
    next_required_approval: WorkflowStep | None = None
    warnings: list[str] = Field(default_factory=list)
