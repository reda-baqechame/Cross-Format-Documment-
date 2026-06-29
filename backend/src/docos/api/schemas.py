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
from docos.services.provenance.duplicates import DuplicateGroup
from docos.services.provenance.health import DocumentHealth
from docos.services.provenance.interface import VersionRef
from docos.services.provenance.readiness import ReadinessReport
from docos.services.provenance.redaction_audit import RedactionAuditReport
from docos.services.provenance.sensitive import SensitiveFinding
from docos.services.provenance.validation import ValidationReport
from docos.services.semantic.classify import Classification
from docos.services.semantic.extract import Extraction
from docos.services.semantic.intelligence import DocumentInsight
from docos.services.semantic.preview import PatchPreview
from docos.services.semantic.reader import Citation
from docos.services.semantic.skills.autopilot import AutopilotReport


class HealthCheck(BaseModel):
    status: str
    deployed_revision: str = "unknown"
    migration_head: str = "unknown"
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
    # Gated-capability truthing: each is False/[] until its external provider/credential is wired,
    # so the UI shows the real state ("Not connected") instead of implying it works.
    esign_configured: bool = False
    idp_configured: bool = False
    handwriting_configured: bool = False
    tts_configured: bool = False
    drm_configured: bool = False
    presence_enabled: bool = True
    cloud_integrations: list[str] = []
    billing_configured: bool = False


class ReadyCheck(BaseModel):
    """Deep readiness probe — unlike ``/health`` this fails (503) when the app cannot actually
    serve document operations: required tables missing, blob storage unwritable, or migrations
    not applied. Railway points its healthcheck here so a broken deploy never reports healthy."""

    ok: bool
    deployed_revision: str = "unknown"
    migration_head: str = "unknown"
    checks: dict[str, str]


# Truth-ledger capability state. The UI/marketing must derive a capability's enablement from this
# state instead of asserting it. A capability is ``verified`` only when a real customer workflow
# produces a correct artifact (a passing production-matrix outcome), never merely an HTTP 200.
CapabilityState = Literal[
    "verified",  # real workflow produces a correct, independently-checked artifact
    "degraded",  # works but at reduced fidelity/quality; honesty warning attached
    "provider_gated",  # needs an external provider/credential not currently configured
    "disabled",  # intentionally off
    "broken",  # currently failing in the production matrix
    "claim_without_proof",  # asserted in the UI but no repeatable proof exists yet
]


class Capability(BaseModel):
    """A single capability's real state, engine, limitations, and proof.

    ``proof_id`` references a named outcome in the production tool-matrix run; ``last_verified_at``
    is when that run last recorded a passing artifact. Both are null when unproven, so a missing
    proof is visible rather than implied.
    """

    id: str
    name: str
    state: CapabilityState
    engine: str
    engine_version: str | None = None
    limitations: list[str] = []
    last_verified_at: datetime | None = None
    proof_id: str | None = None
    warnings: list[str] = []


class CapabilitiesResponse(BaseModel):
    """``GET /api/capabilities`` — the honest map of what the platform actually does.

    Mirrors ``HealthCheck`` (so flags stay in sync) but adds engine/version, limitations, proof
    linkage, and the AGPL/GPL licence risk surface. UI controls and marketing claims must derive
    from this rather than hardcoding "available".
    """

    generated_at: datetime
    privacy_mode: str
    database: str
    max_upload_mb: int
    capabilities: list[Capability]
    engine_versions: dict[str, dict[str, str | None]]
    licence_risks: list[str]
    # The engine + license registry (the "license firewall"): every engine we use or vet, its
    # SPDX license, usage class, capabilities, and whether it is installed in this deployment.
    engines: list[dict] = []


class UploadResponse(BaseModel):
    # In sync mode doc_id/version_id are present immediately. In async mode the response carries a
    # job_id + status instead (doc_id arrives via GET /jobs/{job_id} once the worker finishes).
    doc_id: str | None = None
    version_id: str | None = None
    detected_format: str | None = None
    job_id: str | None = None
    status: str | None = None


class JobStatusResponse(BaseModel):
    """Status of an async ingest/OCR job (the async-pipeline seam).

    Today most work runs synchronously in-request; this read endpoint exposes the ``jobs`` table so
    the frontend can poll progress once heavy parsing/OCR is moved to a worker.
    """

    job_id: str
    kind: str
    status: str  # pending | processing | succeeded | failed
    document_id: str | None = None
    finished: bool = False
    error: str | None = None


class DuplicatesResponse(BaseModel):
    """Near-duplicate document clusters across the caller's library."""

    groups: list[DuplicateGroup]


class DocumentModelResponse(BaseModel):
    document: CanonicalDocument
    version_id: str | None


class DocumentHealthResponse(BaseModel):
    doc_id: str
    health: DocumentHealth


class ReadinessResponse(BaseModel):
    """Send-Ready / Document X-Ray verdict + per-check breakdown for a document."""

    doc_id: str
    report: ReadinessReport


class CleanResponse(BaseModel):
    """Result of a one-shot 'Clean Before You Send': fixes applied + post-clean verdict + proof."""

    doc_id: str
    applied: bool
    new_version_id: str | None
    report: ReadinessReport  # re-run after cleaning
    validation: ValidationReport  # proof the clean copy is sound (redaction unrecoverable, …)


class RedactionAuditResponse(BaseModel):
    """Un-Redact Test verdict: is text still recoverable under this PDF's 'redactions'?"""

    doc_id: str
    audit: RedactionAuditReport


class PurgeResponse(BaseModel):
    """How many of the caller's documents were deleted by a Private-Mode purge."""

    deleted: int


class FillProfileResponse(BaseModel):
    """The caller's saved Fill-Once profile (field-name → value)."""

    data: dict[str, str]


class SaveFillProfileRequest(BaseModel):
    data: dict[str, str]


class AutofillResponse(BaseModel):
    """Result of autofilling a document's blank fields from the saved profile."""

    doc_id: str
    filled: int
    new_version_id: str | None


# ── CLM: clause library + renewals ──────────────────────────────────────────────────────────
class ClauseResponse(BaseModel):
    id: str
    title: str
    body: str
    category: str | None = None


class ClauseListResponse(BaseModel):
    clauses: list[ClauseResponse]


class CreateClauseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    category: str | None = Field(default=None, max_length=100)


class InsertClauseRequest(BaseModel):
    """Insert either a saved clause (by id) or ad-hoc title/body into a document."""

    clause_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=20000)


class InsertClauseResponse(BaseModel):
    doc_id: str
    inserted: int  # number of blocks added
    new_version_id: str | None


class RenewalResponse(BaseModel):
    id: str
    title: str
    due_date: str
    note: str | None = None
    status: str
    doc_id: str | None = None
    urgency: str  # overdue | soon | later


class RenewalListResponse(BaseModel):
    renewals: list[RenewalResponse]


class CreateRenewalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: str = Field(description="ISO date YYYY-MM-DD")
    note: str | None = Field(default=None, max_length=2000)
    doc_id: str | None = None


class RenewalSuggestionsResponse(BaseModel):
    doc_id: str
    due_dates: list[str]


# ── E-signature (gated provider seam) ──────────────────────────────────────────────────────
class SignerInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class SignatureRequestCreate(BaseModel):
    signers: list[SignerInput] = Field(default_factory=list)
    subject: str | None = Field(default=None, max_length=300)


class SignatureRequestResponse(BaseModel):
    id: str
    doc_id: str
    provider: str
    status: str
    signing_url: str | None = None
    detail: str = ""
    legally_binding: bool = False


# ── Cloud integrations (gated OAuth seam) ──────────────────────────────────────────────────
class IntegrationStatus(BaseModel):
    name: str
    label: str
    configured: bool  # OAuth client creds present in this deployment
    connected: bool  # the caller has completed the connect flow (a token is stored)


class IntegrationListResponse(BaseModel):
    integrations: list[IntegrationStatus]


class ConnectResponse(BaseModel):
    authorize_url: str


class IntegrationImportRequest(BaseModel):
    file_url: str = Field(min_length=1, max_length=2048)
    filename: str | None = Field(default=None, max_length=255)


# ── Cloud IDP / handwriting (gated seam) ───────────────────────────────────────────────────
class IdpFieldSchema(BaseModel):
    key: str
    value: str
    confidence: float = 0.0


class IdpExtractResponse(BaseModel):
    doc_id: str
    provider: str  # "textract" | "external" | "local"
    used_provider: bool  # True when a cloud IDP/handwriting model produced the result
    fields: list[IdpFieldSchema]
    detail: str = ""


# ── Live presence (single-node) ────────────────────────────────────────────────────────────
class PresenceBeat(BaseModel):
    viewer_id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="Guest", max_length=80)
    color: str = Field(default="#2451e6", max_length=16)


class ViewerSchema(BaseModel):
    viewer_id: str
    name: str
    color: str
    idle_seconds: float = 0.0


class PresenceResponse(BaseModel):
    doc_id: str
    viewers: list[ViewerSchema]
    ttl_seconds: int


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

    instruction: str | None = Field(default=None, max_length=10_000)
    ops: list[PatchOpDTO] | None = Field(default=None, max_length=1_000)

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


class PatchPlanResponse(BaseModel):
    """A validated, **non-committed** edit plan: the concrete ops + a before/after preview.

    The client shows the preview, then re-submits ``ops`` to ``POST /documents/{id}/patches`` to
    actually apply them. Nothing is mutated or versioned by requesting a plan.
    """

    doc_id: str
    intent: str | None = None
    ops: list[PatchOpDTO]
    preview: PatchPreview


class FindReplaceRequest(BaseModel):
    """Replace every occurrence of ``find`` with ``replace`` across the document."""

    find: str = Field(min_length=1, max_length=512)
    replace: str = Field(default="", max_length=10_000)
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


class AgentRunRequest(BaseModel):
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
