"""RTF adapter (striprtf) — STUB.

Extension point: strip RTF control words to plain text + basic structure, then build
paragraphs/runs much like the TXT adapter but preserving bold/italic where parseable.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


class RtfAdapter(FormatAdapter):
    format_id = "rtf"
    supported_mimes = ("application/rtf", "text/rtf")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        raise NotImplementedError("RtfAdapter.parse — implement with striprtf")

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("RtfAdapter.render_preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("RtfAdapter.export")
