"""Image adapter (Pillow) — STUB.

Extension point: store image bytes via the blob store as a single-page ImageNode,
then hand the page to the OCR & structure service to recover text, tables, and
reading order from scans.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


class ImageAdapter(FormatAdapter):
    format_id = "image"
    supported_mimes = ("image/png", "image/jpeg", "image/tiff")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        raise NotImplementedError("ImageAdapter.parse — store blob + route to OCR service")

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("ImageAdapter.render_preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("ImageAdapter.export")
