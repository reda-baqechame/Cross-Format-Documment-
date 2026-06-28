"""PdfEngine boundary — the single surface for low-level PDF operations.

Goal: stop importing ``fitz`` (PyMuPDF, AGPL-3.0) directly across the codebase. Every PDF
capability goes through this package's module-level functions, dispatched by
``settings.pdf_engine`` to either the current PyMuPDF implementation (the default, unchanged
behaviour) or a permissive implementation (pypdf + pikepdf + pypdfium2).

This mirrors the existing ``pdfium.py`` / ``PDF_RENDER_ENGINE`` seam: a settings switch plus a
factory that picks the concrete engine, so behaviour is identical under the default and the
migration is incremental and reversible.

Capability migration status (per the parity bake-off in ``tests/test_pdfengine_parity.py``):
    page_count / merge / reorder / delete / extract / rotate — permissive parity (pypdf)
    encrypt (AES-256 R6)                              — permissive parity (pikepdf)
    compress                                          — permissive parity (pikepdf linearize)
    text/table extraction, redaction, searchable-PDF  — PyMuPDF only (hard to replace; stays
                                                         behind the boundary, honestly flagged
                                                         in /api/capabilities until parity)

Public API (stable, engine-agnostic):
    page_count, reorder_pages, delete_pages, extract_pages, rotate_pages, merge,
    encrypt_pdf, compress_pdf, watermark_pdf
"""

from __future__ import annotations

from docos.settings import get_settings


def _engine():
    """Resolve the configured PdfEngine module (late import to avoid import-time fitz cost)."""
    engine = get_settings().pdf_engine
    if engine == "permissive":
        from docos.services.docengine.pdfengine import permissive_engine

        return permissive_engine
    # default: pymupdf (current behaviour, unchanged).
    from docos.services.docengine.pdfengine import pymupdf_engine

    return pymupdf_engine


def available_engines() -> list[str]:
    """Which engine implementations are importable in this environment."""
    impls = ["pymupdf"]
    try:
        import pikepdf  # noqa: F401
        import pypdf  # noqa: F401

        impls.append("permissive")
    except Exception:
        pass
    return impls


def active_engine() -> str:
    """The configured engine, falling back to pymupdf when permissive deps are missing."""
    settings = get_settings()
    if settings.pdf_engine == "permissive":
        try:
            import pikepdf  # noqa: F401
            import pypdf  # noqa: F401

            return "permissive"
        except Exception:
            return "pymupdf (fallback: permissive deps not installed)"
    return "pymupdf"


# ── Engine-agnostic façade ─────────────────────────────────────────────────────────────────
# Each function delegates to the configured engine module. The signatures are identical to the
# legacy ``pageops`` module so callers switch by changing an import.

def page_count(pdf: bytes) -> int:
    return _engine().page_count(pdf)


def reorder_pages(pdf: bytes, order: list[int]) -> bytes:
    return _engine().reorder_pages(pdf, order)


def delete_pages(pdf: bytes, pages: list[int]) -> bytes:
    return _engine().delete_pages(pdf, pages)


def extract_pages(pdf: bytes, pages: list[int]) -> bytes:
    return _engine().extract_pages(pdf, pages)


def rotate_pages(pdf: bytes, pages: list[int], degrees: int) -> bytes:
    return _engine().rotate_pages(pdf, pages, degrees)


def merge(pdfs: list[bytes]) -> bytes:
    return _engine().merge(pdfs)


def encrypt_pdf(
    pdf: bytes, user_password: str, owner_password: str | None = None, *, allow_print: bool = True
) -> bytes:
    return _engine().encrypt_pdf(
        pdf, user_password, owner_password, allow_print=allow_print
    )


def compress_pdf(pdf: bytes) -> bytes:
    return _engine().compress_pdf(pdf)


def watermark_pdf(pdf: bytes, text: str) -> bytes:
    return _engine().watermark_pdf(pdf, text)
