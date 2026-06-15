"""Provenance & policy service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.model.patch import ReversiblePatch
from docos.services.provenance.health import DocumentHealth


class VersionRef(BaseModel):
    version_id: str
    parent_id: str | None
    patch_id: str | None
    created_at: datetime


class ProvenancePolicyService(ABC):
    @abstractmethod
    def record_event(self, doc_id: str | None, action: str, *, actor: str, detail: dict) -> None:
        """Append an immutable audit event."""

    @abstractmethod
    def commit_version(
        self, doc: CanonicalDocument, *, patch: ReversiblePatch | None = None
    ) -> str:
        """Persist a content-hashed version snapshot; return the version id."""

    @abstractmethod
    def history(self, doc_id: str) -> list[VersionRef]:
        """Return the version lineage for a document."""

    @abstractmethod
    def compute_health(self, doc: CanonicalDocument) -> DocumentHealth:
        """Compute the document-health panel DTO."""

    @abstractmethod
    def apply_label(self, doc_id: str, label: str) -> None:
        """Attach a sensitivity/policy label to a document."""

    @abstractmethod
    def sanitize_metadata(self, doc: CanonicalDocument) -> ReversiblePatch:
        """Produce a reversible patch that strips risky embedded metadata."""
