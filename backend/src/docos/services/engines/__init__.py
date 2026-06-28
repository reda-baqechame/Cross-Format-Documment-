"""Engine version detection — reports which document-intelligence engines are *actually*
importable at runtime, with their version.

This is the truth source for ``GET /api/capabilities``: the payload describes the live engine
(name + version) rather than what is merely declared in ``pyproject.toml``. Optional seams
(pypdfium2, pypdf, Presidio, PaddleOCR, …) are declared as dependencies but may be absent in a
given deployment, so each is probed lazily and reported as ``None`` when missing.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version


def _dist_version(dist: str) -> str | None:
    """The installed distribution version, or None when the package is absent."""
    try:
        return pkg_version(dist)
    except PackageNotFoundError:
        return None


def pdf_versions() -> dict[str, str | None]:
    """Versions of every PDF-related engine, or ``None`` where the library is not installed.

    ``pymupdf`` is the AGPL dependency being migrated off; ``pypdfium2``/``pypdf``/``pikepdf``
    are the permissive migration targets (optional seams today).
    """
    return {
        "pymupdf": _dist_version("pymupdf"),
        "pypdfium2": _dist_version("pypdfium2"),
        "pypdf": _dist_version("pypdf"),
        "pikepdf": _dist_version("pikepdf"),
        "reportlab": _dist_version("reportlab"),
    }


def parse_ocr_versions() -> dict[str, str | None]:
    """OCR / structure-extraction engine versions."""
    return {
        "pytesseract": _dist_version("pytesseract"),
        "paddleocr": _dist_version("paddleocr"),
        "docling": _dist_version("docling"),
        "pillow": _dist_version("pillow"),
    }


def search_pii_versions() -> dict[str, str | None]:
    """Search + PII-detection engine versions."""
    return {
        "presidio-analyzer": _dist_version("presidio-analyzer"),
        "rapidfuzz": _dist_version("rapidfuzz"),
        "phonenumbers": _dist_version("phonenumbers"),
    }


def all_engine_versions() -> dict[str, dict[str, str | None]]:
    """All engine versions, grouped by lane, for the capabilities payload."""
    return {
        "pdf": pdf_versions(),
        "ocr_structure": parse_ocr_versions(),
        "search_pii": search_pii_versions(),
    }


def agpl_risk() -> list[str]:
    """The set of AGPL/GPL dependencies currently present and load-bearing.

    PyMuPDF (``fitz``) is the known blocker: it is AGPL-3.0 and is imported directly for PDF
    parsing, page-ops, redaction write-back, searchable-PDF writing, and validation. Until the
    PdfEngine migration removes it, every PDF capability carries this licence risk.
    """
    risks: list[str] = []
    if _dist_version("pymupdf") is not None:
        risks.append(
            "pymupdf (AGPL-3.0) is installed and load-bearing for PDF parsing, page-ops, "
            "redaction write-back, searchable-PDF writing, and validation — a closed-SaaS "
            "licence blocker until the PdfEngine migration completes or a commercial licence "
            "is acquired."
        )
    return risks
