"""PDF adapter (PyMuPDF) — STUB.

Extension point: extract text spans with bbox per page (``page.get_text("dict")``),
images (route scans to the OCR service), form fields, and metadata; render previews
via ``page.get_pixmap``; export via an incremental-save patch applier. PDF is the
highest-value, highest-difficulty format, so it is intentionally deferred.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


class PdfAdapter(FormatAdapter):
    format_id = "pdf"
    supported_mimes = ("application/pdf",)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        raise NotImplementedError("PdfAdapter.parse — implement with PyMuPDF text/image extraction")

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("PdfAdapter.render_preview — use page.get_pixmap")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("PdfAdapter.export — apply patches via incremental save")
