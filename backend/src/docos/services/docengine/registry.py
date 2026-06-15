"""Adapter registry — resolves a mime/format to its ``FormatAdapter``."""

from __future__ import annotations

from docos.services.docengine.adapters.docx import DocxAdapter
from docos.services.docengine.adapters.image import ImageAdapter
from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.adapters.pptx import PptxAdapter
from docos.services.docengine.adapters.rtf import RtfAdapter
from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.docengine.adapters.xlsx import XlsxAdapter
from docos.services.docengine.interface import FormatAdapter


class AdapterRegistry:
    def __init__(self, adapters: list[FormatAdapter] | None = None) -> None:
        self._adapters: list[FormatAdapter] = adapters or []

    def register(self, adapter: FormatAdapter) -> None:
        self._adapters.append(adapter)

    def resolve(self, mime: str) -> FormatAdapter:
        for adapter in self._adapters:
            if adapter.can_handle(mime):
                return adapter
        raise LookupError(f"no adapter registered for mime: {mime}")

    def resolve_by_format(self, format_id: str) -> FormatAdapter:
        for adapter in self._adapters:
            if adapter.format_id == format_id:
                return adapter
        raise LookupError(f"no adapter registered for format: {format_id}")


def default_registry() -> AdapterRegistry:
    """All adapters registered. TXT, DOCX & PDF are functional; the rest are stubs."""
    return AdapterRegistry(
        [
            TxtAdapter(),
            DocxAdapter(),
            PdfAdapter(),
            XlsxAdapter(),
            PptxAdapter(),
            RtfAdapter(),
            ImageAdapter(),
        ]
    )
