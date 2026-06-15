"""PPTX adapter (python-pptx) — STUB.

Extension point: map each slide to a page, each shape's text frame to paragraphs/runs,
and pictures to ImageNodes (with alt text where present).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class PptxAdapter(FormatAdapter):
    format_id = "pptx"
    supported_mimes = (_PPTX_MIME,)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        raise NotImplementedError("PptxAdapter.parse — implement with python-pptx")

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("PptxAdapter.render_preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("PptxAdapter.export")
