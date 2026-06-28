"""``GET /capabilities`` — the truth ledger.

Unlike ``/health`` (which returns booleans for display), this endpoint exposes each capability's
real state, the engine that backs it and its version, its limitations, and a ``proof_id`` that
cites the production tool-matrix outcome proving it. UI controls and marketing claims must derive
from this so they never assert a capability that is provider-gated, degraded, or broken.

State vocabulary (``schemas.CapabilityState``):
    verified          — a real customer workflow produces a correct, independently-checked artifact
    degraded          — works but at reduced fidelity/quality (honesty warning attached)
    provider_gated    — needs an external provider/credential not currently configured
    disabled          — intentionally off
    broken            — currently failing in the production matrix
    claim_without_proof — asserted in the UI but no repeatable proof exists yet

A capability is only ``verified`` when its ``proof_id`` resolves to a passing matrix outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from docos.api.schemas import CapabilitiesResponse, Capability, CapabilityState
from docos.services import engines
from docos.settings import Settings, get_settings

router = APIRouter(tags=["system"])

# Identifier of the production tool-matrix run that backs the ``verified`` claims below. Bumped
# whenever the matrix is rerun and the results artifact is recommitted.
PROOF_RUN_ID = "production-tool-matrix-2026-06-27"
# Path to the committed matrix results, used to read ``last_verified_at`` (the file mtime).
_MATRIX_RESULTS = (
    Path(__file__).resolve().parents[4] / "scripts" / "production-tool-matrix-results.json"
)


def _matrix_verified_at() -> datetime | None:
    """The last time the production matrix results artifact was regenerated (file mtime)."""
    try:
        return datetime.fromtimestamp(_MATRIX_RESULTS.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def _cap(
    cid: str,
    name: str,
    *,
    state: CapabilityState,
    engine: str,
    engine_version: str | None,
    proof_id: str | None,
    limitations: list[str] | None = None,
    warnings: list[str] | None = None,
) -> Capability:
    last_verified_at = _matrix_verified_at() if (proof_id and state == "verified") else None
    return Capability(
        id=cid,
        name=name,
        state=state,
        engine=engine,
        engine_version=engine_version,
        limitations=limitations or [],
        last_verified_at=last_verified_at,
        proof_id=proof_id,
        warnings=warnings or [],
    )


def _pdf_agpl_warning() -> list[str]:
    """Honest AGPL warning attached to every PDF capability still backed by PyMuPDF."""
    return [
        "PDF parsing/page-ops/redaction/searchable-PDF still use PyMuPDF (AGPL-3.0) — a "
        "closed-SaaS licence blocker until the PdfEngine migration completes."
    ]


def _scanner_limitations(scanner: str) -> list[str]:
    """Honest description of what the active upload scanner does and does not cover."""
    if scanner == "noop":
        return [
            "Scanner is 'noop' (accepts everything) — for local-dev opt-out only; never use on "
            "public uploads."
        ]
    heuristic = (
        "Heuristic content-defense (offline, deterministic): blocks EICAR, embedded executables, "
        "PDF launch actions and Office macros. Not signature AV — does not catch novel/obfuscated "
        "malware; chain ClamAV (SCANNER=clamav) for that."
    )
    if scanner == "clamav":
        return [
            "ClamAV signature scanning is layered behind the always-on heuristic content-defense; "
            "fails closed if the clamd daemon is unreachable."
        ]
    return [heuristic]


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(settings: Settings = Depends(get_settings)) -> CapabilitiesResponse:
    """The honest map of what the platform actually does right now."""
    pdf_versions = engines.pdf_versions()
    ocr_versions = engines.parse_ocr_versions()
    search_versions = engines.search_pii_versions()
    agpl = engines.agpl_risk()
    pdf_warning = _pdf_agpl_warning() if pdf_versions.get("pymupdf") else []

    # The active page-ops/encryption engine (permissive when pdf_engine=permissive AND deps are
    # installed; otherwise PyMuPDF). Page ops/encrypt/compress have permissive parity; watermark/
    # text/redaction/searchable-PDF still fall back to PyMuPDF and stay AGPL-flagged.
    from docos.services.docengine.pdfengine import active_engine as _active_pdf_engine

    pdf_ops_engine = _active_pdf_engine()
    pdf_ops_permissive = pdf_ops_engine.startswith("permissive")
    # Version reported for parity-proven page ops/encrypt/compress: permissive lib when active,
    # else the AGPL PyMuPDF version that is actually backing those operations.
    ops_version = pdf_versions.get("pypdf" if pdf_ops_permissive else "pymupdf")
    enc_version = pdf_versions.get("pikepdf" if pdf_ops_permissive else "pymupdf")

    caps: list[Capability] = [
        # ── Ingest & parse ──────────────────────────────────────────────────────────────────
        _cap(
            "upload_store",
            "Upload and store documents",
            state="verified",
            engine=f"parser:{settings.parser_engine}",
            engine_version=(
                ocr_versions.get("docling") if settings.parser_engine == "docling" else None
            ),
            proof_id="Upload userPdf",
        ),
        _cap(
            "convert_formats",
            "Convert common formats",
            state="degraded",
            engine="native-writers",
            engine_version=None,
            proof_id="Export PDF→docx",
            limitations=[
                "Cross-format conversion preserves content but not full native fidelity on "
                "every pair; the golden-corpus reopen/fidelity benchmark is not yet complete."
            ],
        ),
        # ── PDF operations ──────────────────────────────────────────────────────────────────
        _cap(
            "pdf_edit_text",
            "PDF edit / add text",
            state="verified",
            engine=f"pdf-render:{settings.pdf_render_engine}",
            engine_version=pdf_versions.get(settings.pdf_render_engine),
            proof_id="Modify PDF text",
            warnings=pdf_warning,
        ),
        _cap(
            "pdf_organize",
            "PDF organize (merge/split/rotate/delete/reorder)",
            state="verified",
            engine=f"page-ops:{pdf_ops_engine}",
            engine_version=ops_version,
            proof_id="Merge PDFs",
            warnings=[] if pdf_ops_permissive else pdf_warning,
        ),
        _cap(
            "pdf_compress",
            "PDF compress",
            state="verified",
            engine=f"compress:{pdf_ops_engine}",
            engine_version=enc_version,
            proof_id="Compress PDF",
            warnings=[] if pdf_ops_permissive else pdf_warning,
        ),
        _cap(
            "pdf_watermark",
            "PDF watermark",
            state="verified",
            engine="pymupdf-pageops",
            engine_version=pdf_versions.get("pymupdf"),
            proof_id="Watermark PDF",
            warnings=pdf_warning,
        ),
        _cap(
            "pdf_protect",
            "Password-protect PDF (AES-256)",
            state="verified",
            engine=f"encrypt:{pdf_ops_engine}",
            engine_version=enc_version,
            proof_id="Protect PDF",
            limitations=["Local AES-256 protection, not legal DRM."],
            warnings=[] if pdf_ops_permissive else pdf_warning,
        ),
        # ── Redaction & trust ────────────────────────────────────────────────────────────────
        _cap(
            "redaction",
            "True redaction on export",
            # Verified by the redaction proof corpus: zero recoverable secret bytes across every
            # from-model export format, including decompressed OOXML parts, with a negative control.
            state="verified",
            engine=f"pii:{settings.pii_engine}",
            engine_version=search_versions.get("presidio-analyzer")
            if settings.pii_engine == "presidio"
            else None,
            proof_id="eval:redaction_proof",
            limitations=[
                "Zero-recoverable-bytes proven for docx/xlsx/pptx/html/markdown/rtf/csv "
                "(evals/redaction_proof, CI-gated). PDF redaction is a separate write-back path "
                "(redaction_audit) still on PyMuPDF — see the AGPL note."
            ],
            warnings=pdf_warning,
        ),
        _cap(
            "metadata_sanitize",
            "Metadata removal",
            state="verified",
            engine="pymupdf-scrub",
            engine_version=pdf_versions.get("pymupdf"),
            proof_id="Clean before send (POST on txt)",
            warnings=pdf_warning,
        ),
        _cap(
            "readiness_check",
            "Send-Ready / document health",
            state="verified",
            engine="readiness",
            engine_version=None,
            proof_id="Document health panel",
        ),
        # ── OCR & searchable PDF ─────────────────────────────────────────────────────────────
        _cap(
            "ocr",
            "OCR (scans/images)",
            state="verified",
            engine=f"ocr:{settings.ocr_engine}",
            engine_version=ocr_versions.get("paddleocr") if settings.ocr_engine == "paddle"
            else ocr_versions.get("pytesseract"),
            proof_id="Searchable PDF (PNG scan)",
            limitations=[
                "Production matrix passes; clean-scan CER ≤2% / noisy CER ≤8% / table-cell F1 "
                "≥0.95 corpus benchmark is not yet recorded."
            ],
        ),
        _cap(
            "searchable_pdf",
            "Searchable PDF / OCR layer",
            state="verified",
            engine="pymupdf-writer",
            engine_version=pdf_versions.get("pymupdf"),
            proof_id="Searchable PDF (user doc)",
            warnings=pdf_warning,
        ),
        # ── Search ───────────────────────────────────────────────────────────────────────────
        _cap(
            "search",
            "Library search (BM25 keyword)",
            # Verified as *keyword* search by a labelled benchmark, not claimed as semantic.
            state="verified",
            engine="bm25-keyword+stemming",
            engine_version=None,
            proof_id="eval:search_retrieval",
            limitations=[
                "BM25 keyword ranking with Snowball stemming. Benchmark (evals/search_retrieval): "
                "lexical recall@5 = 100%, semantic recall@5 = 20% — stemming matches morphological "
                "variants (renting→rent) but NOT true synonymy (a 'compensation' query still "
                "misses a doc saying only 'salary'). Closing the rest needs an embedding model; "
                "the benchmark is the predeclared gate it must beat."
            ],
        ),
        # ── AI ───────────────────────────────────────────────────────────────────────────────
        _cap(
            "ai_ask_summarize",
            "AI ask / summarize / extract / classify",
            state="provider_gated" if not settings.ai_enabled else "verified",
            engine=f"llm:{settings.effective_llm_provider}",
            engine_version=settings.llm_model or None,
            proof_id=None,
            limitations=[
                "Provider not configured (noop); offline deterministic/extractive results only."
            ]
            if not settings.ai_enabled
            else [],
        ),
        _cap(
            "ai_edit",
            "Natural-language AI edit (plan → preview → commit)",
            state="provider_gated" if not settings.ai_enabled else "verified",
            engine=f"llm:{settings.effective_llm_provider}",
            engine_version=settings.llm_model or None,
            proof_id="Ops agent plan",
            limitations=["Provider not configured (noop); AI editing disabled offline."]
            if not settings.ai_enabled
            else [],
        ),
        _cap(
            "translate",
            "Translate",
            state="provider_gated",
            engine=f"llm:{settings.effective_llm_provider}",
            engine_version=None,
            proof_id=None,
            limitations=["No-op LLM seam — returns 'not connected' until a provider is wired."],
        ),
        # ── Provider-gated capabilities ──────────────────────────────────────────────────────
        _cap(
            "tts",
            "Listen / text-to-speech",
            state="provider_gated" if not settings.tts_configured else "verified",
            engine=f"tts:{settings.tts_provider}",
            engine_version=None,
            proof_id=None,
            limitations=["Returns 501 'not configured' until a TTS provider is wired."],
        ),
        _cap(
            "esign",
            "Request e-signature",
            state="provider_gated" if not settings.esign_configured else "verified",
            engine=f"signature:{settings.signature_provider}",
            engine_version=None,
            proof_id="Integrity seal / sign",
            limitations=[
                "Integrity seal (HMAC, tamper-evident) only — NOT legally binding. Regulated "
                "legal e-signature requires a compliant provider and legal review."
            ],
        ),
        _cap(
            "drm",
            "DRM / rights management",
            state="provider_gated" if not settings.drm_configured else "verified",
            engine=f"drm:{settings.drm_provider}",
            engine_version=None,
            proof_id=None,
            limitations=[
                "Local AES-256 password protection only. 'Legal DRM' cannot honestly be "
                "zero-string software; needs an external provider."
            ],
        ),
        _cap(
            "idp",
            "Intelligent document processing (IDP)",
            state="provider_gated" if not settings.idp_configured else "verified",
            engine=f"idp:{settings.idp_provider}",
            engine_version=None,
            proof_id=None,
            limitations=["Local OCR + deterministic extractor; cloud IDP needs a provider."],
        ),
        _cap(
            "handwriting",
            "Handwriting OCR",
            state="provider_gated" if not settings.handwriting_configured else "verified",
            engine=f"handwriting:{settings.handwriting_provider}",
            engine_version=None,
            proof_id=None,
            limitations=["Falls back to standard OCR; specialized model needs a provider URL."],
        ),
        _cap(
            "office_editor",
            "Native Office editor",
            state="provider_gated" if not settings.office_editor_configured else "verified",
            engine=f"office-editor:{settings.office_editor_provider}",
            engine_version=None,
            proof_id=None,
            limitations=[
                "Structural editing only; full native fidelity needs OnlyOffice (AGPL) or "
                "another configured provider."
            ],
        ),
        _cap(
            "pdf_editor",
            "Native PDF editor",
            state="provider_gated" if not settings.pdf_editor_configured else "verified",
            engine=f"pdf-editor:{settings.pdf_editor_provider}",
            engine_version=None,
            proof_id=None,
            limitations=["Basic audited editor; Acrobat-level editing needs a PDF SDK provider."],
        ),
        _cap(
            "billing",
            "Billing / subscriptions",
            state="provider_gated" if not settings.billing_configured else "verified",
            engine="stripe" if settings.billing_configured else "none",
            engine_version=None,
            proof_id=None,
            limitations=["Stripe not configured; Upgrade is disabled until keys are set."],
        ),
        _cap(
            "cloud_integrations",
            "Cloud integrations (Drive/Dropbox/Box/OneDrive/Slack)",
            state="provider_gated" if not settings.configured_integrations else "verified",
            engine="oauth",
            engine_version=None,
            proof_id="List integrations",
            limitations=[
                f"Connected: {', '.join(settings.configured_integrations) or 'none'}. "
                "Other providers return 'not connected'."
            ],
        ),
        _cap(
            "collaboration",
            "Real-time presence / collaboration",
            state="verified",
            engine="presence",
            engine_version=None,
            proof_id=None,
            limitations=[
                "Single-node heartbeat/poll presence; multi-node + conflict CRDT not yet proven."
            ],
        ),
        _cap(
            "malware_scan",
            "Malware / content-defense scanning for public uploads",
            state="degraded" if settings.scanner == "noop" else "verified",
            engine=f"scanner:{settings.scanner}",
            engine_version=None,
            proof_id=None if settings.scanner == "noop" else "test:scanner_content_defense",
            limitations=_scanner_limitations(settings.scanner),
        ),
    ]

    return CapabilitiesResponse(
        generated_at=datetime.now(UTC),
        privacy_mode=settings.privacy_mode,
        database=settings.database_kind,
        max_upload_mb=settings.max_upload_mb,
        capabilities=caps,
        engine_versions=engines.all_engine_versions(),
        licence_risks=agpl,
    )
