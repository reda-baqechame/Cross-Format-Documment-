"""Adapter registry — resolves a mime/format to its ``FormatAdapter``."""

from __future__ import annotations

from docos.services.docengine.adapters.csv import CsvAdapter
from docos.services.docengine.adapters.docx import DocxAdapter
from docos.services.docengine.adapters.html import HtmlAdapter
from docos.services.docengine.adapters.image import ImageAdapter
from docos.services.docengine.adapters.markdown import MarkdownAdapter
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


def default_registry(parser_engine: str = "native") -> AdapterRegistry:
    """All adapters registered and functional (image text recovery needs Tesseract).

    When ``parser_engine="docling"`` the PDF/DOCX/PPTX/XLSX adapters are swapped for Docling-backed
    variants that override only ``parse`` (export/preview stay native) and fall back to native when
    Docling isn't installed — so the registry is identical in shape regardless of engine.
    """
    docx: DocxAdapter
    pdf: PdfAdapter
    xlsx: XlsxAdapter
    pptx: PptxAdapter
    if parser_engine == "docling":
        from docos.services.docengine.adapters.docling import (
            DoclingDocxAdapter,
            DoclingPdfAdapter,
            DoclingPptxAdapter,
            DoclingXlsxAdapter,
        )

        docx, pdf, xlsx, pptx = (
            DoclingDocxAdapter(),
            DoclingPdfAdapter(),
            DoclingXlsxAdapter(),
            DoclingPptxAdapter(),
        )
    else:
        docx, pdf, xlsx, pptx = DocxAdapter(), PdfAdapter(), XlsxAdapter(), PptxAdapter()
    return AdapterRegistry(
        [
            TxtAdapter(),
            MarkdownAdapter(),
            CsvAdapter(),
            HtmlAdapter(),
            docx,
            pdf,
            xlsx,
            pptx,
            RtfAdapter(),
            ImageAdapter(),
        ]
    )
