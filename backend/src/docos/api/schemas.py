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
from docos.services.provenance.health import DocumentHealth
from docos.services.provenance.interface import VersionRef
from docos.services.provenance.sensitive import SensitiveFinding
from docos.services.semantic.reader import Citation


class HealthCheck(BaseModel):
    status: str
    privacy_mode: str
    blob_backend: str
    db: str


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
