"""PDF page operations — merge, split, reorder, rotate, delete, compress, encrypt, watermark.

This module is now a thin façade over the ``pdfengine`` boundary
(:mod:`docos.services.docengine.pdfengine`), selected by ``settings.pdf_engine``. The concrete
implementations live in ``pdfengine/pymupdf_engine.py`` (the AGPL default, unchanged behaviour)
and ``pdfengine/permissive_engine.py`` (pypdf + pikepdf, parity-proven for page ops/encrypt/
compress). Routing page operations through the boundary is step 2 of the migration off AGPL
PyMuPDF; text/table extraction, redaction, and searchable-PDF writing still import fitz in
their own modules until their permissive replacements reach fidelity parity.

Routes compose these *after* the canonical write-back, so edits and redactions are already
burned in before pages are rearranged — a one-stop pipeline rather than a separate tool.
"""

from __future__ import annotations

from docos.services.docengine.pdfengine import (
    compress_pdf,
    delete_pages,
    encrypt_pdf,
    extract_pages,
    merge,
    page_count,
    reorder_pages,
    rotate_pages,
    watermark_pdf,
)

__all__ = [
    "compress_pdf",
    "delete_pages",
    "encrypt_pdf",
    "extract_pages",
    "merge",
    "page_count",
    "reorder_pages",
    "rotate_pages",
    "watermark_pdf",
]
