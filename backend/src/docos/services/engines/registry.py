"""Engine + license registry — the governance layer (the "license firewall").

The platform's strategy is to absorb the best permissively-licensed document engines without ever
poisoning the closed-SaaS core with copyleft/source-available code. This registry is the single,
auditable source of truth for *every* engine we use or plan to use: its SPDX license, a usage
class, what it can do, and how it integrates. ``GET /api/capabilities`` surfaces it and the CI
license gate (``scripts/check_licenses.py``) enforces it, so a forbidden engine can never silently
become load-bearing.

License classes:
  * ``safe_core``            — MIT/Apache/BSD/ISC/HPND/PSF: embed freely in the proprietary core.
  * ``safe_with_conditions`` — weak/file-level copyleft (MPL, LGPL via dynamic link): allowed,
                               don't modify-and-ship the library itself; isolate where prudent.
  * ``external_service_only``— copyleft that's fine only as a separate network service the customer
                               runs (e.g. AGPL office servers), never linked into our core.
  * ``commercial_required``  — needs a paid/commercial license for SaaS use (or model weights carry
                               field-of-use restrictions); off until licensed.
  * ``avoid``                — AGPL/SSPL/etc. linked into the core: not allowed (tracked exceptions
                               only, e.g. the PyMuPDF migration in flight).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from typing import Literal

LicenseClass = Literal[
    "safe_core",
    "safe_with_conditions",
    "external_service_only",
    "commercial_required",
    "avoid",
]
IntegrationMode = Literal["python", "model", "service"]


@dataclass(frozen=True)
class EngineSpec:
    name: str
    dist: str | None  # PyPI distribution to probe for "installed" + version (None = not pip)
    spdx: str
    license_class: LicenseClass
    capabilities: tuple[str, ...]
    integration_mode: IntegrationMode = "python"
    notes: str = ""


# The catalogue. Licenses verified against project metadata / upstream (June 2026). Additive: this
# documents both engines in use today and vetted candidates from the research shortlist.
REGISTRY: tuple[EngineSpec, ...] = (
    # ── PDF (permissive migration targets, in the core today) ──
    EngineSpec("pypdfium2", "pypdfium2", "Apache-2.0 OR BSD-3-Clause", "safe_core",
               ("pdf_render", "pdf_text"), notes="Google PDFium; self-contained wheel."),
    EngineSpec("pypdf", "pypdf", "BSD-3-Clause", "safe_core", ("pdf_pageops", "pdf_text")),
    EngineSpec("reportlab", "reportlab", "BSD-3-Clause", "safe_core",
               ("pdf_write", "searchable_pdf", "overlay")),
    EngineSpec("pikepdf", "pikepdf", "MPL-2.0", "safe_with_conditions",
               ("pdf_encrypt", "pdf_linearize", "pdf_streams"), notes="qpdf binding."),
    EngineSpec("pdfplumber", "pdfplumber", "MIT", "safe_core", ("pdf_text", "pdf_tables"),
               notes="char-level text + table geometry (parse fallback)."),
    EngineSpec("pymupdf", "pymupdf", "AGPL-3.0", "avoid",
               ("pdf_parse", "pdf_pageops", "pdf_redact", "searchable_pdf"),
               notes="AGPL — tracked for removal via the PdfEngine migration (ADR-002)."),
    # ── OCR / structure ──
    EngineSpec("pytesseract", "pytesseract", "Apache-2.0", "safe_core", ("ocr",),
               notes="Tesseract is Apache-2.0; bundled default."),
    EngineSpec("paddleocr", "paddleocr", "Apache-2.0", "safe_core",
               ("ocr", "layout", "tables", "ocr_vl"), notes="PaddleOCR / PaddleOCR-VL."),
    EngineSpec("docling", "docling", "MIT", "safe_core",
               ("parse", "layout", "tables", "reading_order"), notes="IBM Docling."),
    EngineSpec("olmocr", "olmocr", "Apache-2.0", "safe_core", ("ocr", "pdf_to_markdown"),
               integration_mode="model", notes="AllenAI olmOCR-2; weights downloaded at runtime."),
    EngineSpec("qwen2.5-vl", None, "Apache-2.0", "safe_core",
               ("ocr_vl", "tables", "forms", "vqa"), integration_mode="model",
               notes="Qwen2.5-VL weights (Apache-2.0); messy-layout/handwriting fallback."),
    EngineSpec("got-ocr2", None, "Apache-2.0", "safe_core", ("ocr_vl",),
               integration_mode="model", notes="GOT-OCR 2.0 weights (Apache-2.0)."),
    EngineSpec("magika", "magika", "Apache-2.0", "safe_core", ("file_type_detection",),
               integration_mode="model", notes="Google Magika; small bundled model."),
    EngineSpec("pillow", "pillow", "HPND", "safe_core", ("image_io",)),
    # ── search / PII ──
    EngineSpec("fastembed", "fastembed", "Apache-2.0", "safe_core", ("embeddings",),
               integration_mode="model", notes="ONNX; serves bge-small-en-v1.5 (MIT)."),
    EngineSpec("presidio-analyzer", "presidio-analyzer", "MIT", "safe_core", ("pii_ner",)),
    EngineSpec("rapidfuzz", "rapidfuzz", "MIT", "safe_core", ("fuzzy_match",)),
    EngineSpec("phonenumbers", "phonenumbers", "Apache-2.0", "safe_core", ("phone_validation",)),
    EngineSpec("snowballstemmer", "snowballstemmer", "BSD-3-Clause", "safe_core", ("stemming",)),
    # ── conversion / office (service or restricted) ──
    EngineSpec("gotenberg", None, "MIT", "safe_core", ("convert_office_pdf", "html_pdf"),
               integration_mode="service",
               notes="MIT API server; isolates LibreOffice/Chromium as a separate service."),
    EngineSpec("univer", None, "Apache-2.0", "safe_core", ("sheet_edit", "doc_edit", "slide_edit"),
               integration_mode="service", notes="Frontend office SDK (JS)."),
    EngineSpec("onlyoffice", None, "AGPL-3.0", "external_service_only",
               ("office_edit", "collaboration"), integration_mode="service",
               notes="AGPL — optional self-hosted external editor only; never linked into core."),
    EngineSpec("ocrmypdf", "ocrmypdf", "MPL-2.0", "safe_with_conditions", ("searchable_pdf",),
               notes="MPL-2.0; note: pulls Ghostscript (AGPL) — use the qpdf path or isolate."),
    # ── restricted (off until licensed) ──
    EngineSpec("surya", None, "Apache-2.0 (code) / OpenRAIL (weights)", "commercial_required",
               ("ocr_vl", "layout"), integration_mode="model",
               notes="Model weights carry usage restrictions; needs a commercial license."),
    EngineSpec("marker", None, "GPL/commercial", "commercial_required", ("pdf_to_markdown",),
               integration_mode="model", notes="Commercial self-host license required."),
)

_BY_NAME = {e.name: e for e in REGISTRY}

# Installed "avoid"/"commercial_required" engines allowed only with a documented, tracked reason.
EXCEPTIONS: dict[str, str] = {
    "pymupdf": "AGPL, load-bearing for PDF today; tracked for removal in the PdfEngine migration "
    "(ADR-002 / docs/roadmap-100x.md).",
}


def _installed_version(dist: str | None) -> str | None:
    if not dist:
        return None
    try:
        return pkg_version(dist)
    except PackageNotFoundError:
        return None


def engine(name: str) -> EngineSpec | None:
    return _BY_NAME.get(name)


def registry_report() -> list[dict]:
    """Each engine with its license, class, capabilities, and whether it is installed here."""
    out: list[dict] = []
    for e in REGISTRY:
        version = _installed_version(e.dist)
        out.append(
            {
                "name": e.name,
                "spdx": e.spdx,
                "license_class": e.license_class,
                "capabilities": list(e.capabilities),
                "integration_mode": e.integration_mode,
                "installed": version is not None,
                "version": version,
                "notes": e.notes,
            }
        )
    return out


def forbidden_installed() -> list[tuple[str, str]]:
    """Installed engines whose class forbids embedding (avoid/commercial_required) and that are NOT
    in the documented EXCEPTIONS. Empty list = the license firewall is clean."""
    bad: list[tuple[str, str]] = []
    for e in REGISTRY:
        if e.license_class in ("avoid", "commercial_required") and _installed_version(e.dist):
            if e.name in EXCEPTIONS:
                continue
            bad.append((e.name, f"{e.spdx} [{e.license_class}]"))
    return bad
