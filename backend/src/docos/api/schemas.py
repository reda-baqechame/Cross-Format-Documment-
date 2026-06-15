"""Request/response DTOs.

These (plus the canonical model) define the OpenAPI schema that ``make codegen``
turns into ``packages/shared-types/src/generated.ts`` — the single source of truth
shared with the frontend.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.provenance.health import DocumentHealth
from docos.services.provenance.interface import VersionRef


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


class PatchRequest(BaseModel):
    instruction: str


class PatchResponse(BaseModel):
    doc_id: str
    patch_id: str
    applied: bool
    new_version_id: str | None
    intent: str | None
