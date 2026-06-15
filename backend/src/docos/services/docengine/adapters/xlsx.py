"""XLSX adapter (openpyxl) — STUB.

Extension point: map each worksheet to a page, each used range to a TableNode, and
cells to TableCellNodes (preserving number formats/formulas in ``attrs``).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class XlsxAdapter(FormatAdapter):
    format_id = "xlsx"
    supported_mimes = (_XLSX_MIME,)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        raise NotImplementedError("XlsxAdapter.parse — implement with openpyxl")

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("XlsxAdapter.render_preview")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("XlsxAdapter.export")
