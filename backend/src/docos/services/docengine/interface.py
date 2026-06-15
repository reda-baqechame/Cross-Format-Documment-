"""``FormatAdapter`` — one implementation per file format.

An adapter is the only place that knows a format's binary details. It maps that
format both ways against the canonical model, so the rest of the system is
format-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from docos.model.document import CanonicalDocument
from docos.storage.blob import BlobStore


class FormatAdapter(ABC):
    format_id: str
    supported_mimes: tuple[str, ...]

    def can_handle(self, mime: str) -> bool:
        return mime in self.supported_mimes

    @abstractmethod
    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        """Parse raw bytes into a canonical document."""

    @abstractmethod
    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        """Render a raster/SVG backdrop for a page (visual aid; model stays source of truth)."""

    @abstractmethod
    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        """Serialize the canonical document back out to bytes in ``target_mime``."""
