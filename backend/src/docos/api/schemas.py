"""Request/response DTOs.

These (plus the canonical model) define the OpenAPI schema that ``make codegen``
turns into ``packages/shared-types/src/generated.ts`` — the single source of truth
shared with the frontend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from docos.model.document import CanonicalDocument
from docos.model.patch import PatchOp
from docos.services.provenance.diff import DiffResult
from docos.services.provenance.health import DocumentHealth
from docos.services.provenance.interface import VersionRef
from docos.services.provenance.sensitive import SensitiveFinding
from docos.services.semantic.classify import Classification
from docos.services.semantic.extract import Extraction
from docos.services.semantic.reader import Citation


class HealthCheck(BaseModel):
    status: str
    privacy_mode: str
    blob_backend: str
    db: str
    # AI features (Ask/Summarize/Translate/natural-language edit) are real only when an LLM
    # provider is configured; the UI uses this to show their true state instead of failing silently.
    ai_enabled: bool = False
    llm_provider: str = "noop"


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
    pages: list[int] = Field(min_length=1)
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


class FieldsResponse(BaseModel):
    doc_id: str
    fields: list[FieldInfo]


class FillFieldRequest(BaseModel):
    node_id: str
    value: str = Field(max_length=5000)
