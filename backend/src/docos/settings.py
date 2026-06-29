"""Application configuration.

Privacy mode and backend choices are config, not code: switching ``PRIVACY_MODE``
or ``BLOB_BACKEND`` swaps concrete service implementations behind the interfaces.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PrivacyMode = Literal["offline", "enterprise", "cloud"]
BlobBackend = Literal["local", "s3"]
LLMProvider = Literal["noop", "openai", "anthropic"]
EmbeddingProvider = Literal["none", "openai", "local"]
Scanner = Literal["heuristic", "clamav", "noop"]
BlobEncryption = Literal["none", "aesgcm"]
OfficeEditorProvider = Literal["local", "onlyoffice"]
PdfEditorProvider = Literal["basic", "external"]
# Gated-capability provider switches. Each defaults to an honest local/off state and activates
# only when its provider URL/key/credential is configured (the seam pattern used across the app).
SignatureProvider = Literal["seal", "external"]
IdpProvider = Literal["local", "textract", "external"]
HandwritingProvider = Literal["none", "external"]
TtsProvider = Literal["none", "external"]
DrmProvider = Literal["none", "external"]
CollabBackend = Literal["memory", "redis"]
# Document-intelligence engine switches. Each defaults to the built-in implementation that
# works offline with zero extra dependencies, and upgrades to a richer engine only when that
# engine is installed/configured (the same activatable-seam pattern used across the app).
ParserEngine = Literal["native", "docling"]
OcrEngine = Literal["tesseract", "paddle", "consensus"]
IngestMode = Literal["sync", "async"]
PiiEngine = Literal["regex", "presidio"]
PdfRenderEngine = Literal["pymupdf", "pdfium"]
# Low-level PDF operations engine (page ops, encryption, compress). ``pymupdf`` (default) keeps
# the current AGPL behaviour; ``permissive`` routes the parity-proven subset (merge/split/
# reorder/rotate/delete/encrypt/compress) to pypdf+pikepdf and falls back to PyMuPDF for the
# capabilities not yet migrated (watermark/text-extract/redaction/searchable-PDF).
PdfEngine = Literal["pymupdf", "permissive"]

# Built-in upload catalog — merged when ALLOWED_MIME_TYPES is a partial Railway override.
_CATALOG_MIME_TYPES = (
    "text/plain,"
    "text/markdown,"
    "text/x-markdown,"
    "text/csv,"
    "application/csv,"
    "text/html,"
    "application/xhtml+xml,"
    "application/pdf,"
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
    "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
    "application/rtf,"
    "image/png,"
    "image/jpeg,"
    "image/tiff,"
    "message/rfc822,"
    "application/json,"
    "text/json,"
    "application/xml,"
    "text/xml"
)
_CATALOG_MIMES = frozenset(m.strip() for m in _CATALOG_MIME_TYPES.split(",") if m.strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    privacy_mode: PrivacyMode = "offline"
    app_env: Literal["dev", "staging", "production"] = "dev"

    # observability. ``human`` (default) is readable in dev; ``json`` emits one JSON line per log
    # record for production aggregation. Sentry error tracking activates only when a DSN is set.
    log_format: Literal["human", "json"] = "human"
    sentry_dsn: str | None = None

    # Source revision injected by Railway (with common fallbacks for other build systems). This is
    # surfaced by /health and /ready so release automation can prove it is testing the intended
    # deployment rather than a healthy but stale container.
    railway_git_commit_sha: str | None = None
    source_commit: str | None = None
    git_commit_sha: str | None = None

    # CORS allow-list for the browser app (comma-separated origins).
    cors_origins: str = "http://localhost:3100"

    # storage
    blob_backend: BlobBackend = "local"
    local_blob_dir: str = "./data/blobs"
    # application-level encryption-at-rest. ``none`` (offline default) stores plaintext;
    # ``aesgcm`` wraps the backend with AES-256-GCM keyed by BLOB_ENCRYPTION_KEY (or, if
    # unset, derived from SIGNING_SECRET).
    blob_encryption: BlobEncryption = "none"
    blob_encryption_key: str | None = None
    s3_endpoint_url: str | None = None
    s3_bucket: str = "docos"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # infra
    database_url: str = "postgresql+psycopg://docos:docos@localhost:5432/docos"
    redis_url: str = "redis://localhost:6379/0"

    # llm
    llm_provider: LLMProvider = "noop"
    # Override the model per provider (e.g. a cheaper model for high-volume Q&A). Empty =
    # the provider client's own default.
    llm_model: str = ""
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # embeddings / semantic search (default-off: retrieval stays deterministic BM25 until a
    # provider is configured, then semantic ranking turns on, fused with BM25 — never replacing
    # it). ``openai`` needs OPENAI_API_KEY; ``local`` runs fully offline (no key) via fastembed +
    # BAAI/bge-small-en-v1.5 — install with ``uv sync --extra embeddings``.
    embedding_provider: EmbeddingProvider = "none"
    embedding_model: str = ""
    # Persistent, content-addressed embedding cache so vectors survive restarts / multi-process
    # deploys (the per-process LRU sits on top). Set empty to disable the on-disk layer.
    embedding_cache_dir: str = "./data/embeddings"

    # e-signature (HMAC key; override in production via SIGNING_SECRET)
    signing_secret: str = "docos-dev-signing-secret"

    # upload scanning. ``heuristic`` (the default) is a deterministic, fully-offline content-defense
    # control that blocks EICAR, embedded executables, PDF launch actions and Office macros — no
    # external infra, so public uploads are always inspected. ``clamav`` additionally streams to a
    # clamd daemon (signature AV) and fails closed if unreachable. ``noop`` accepts everything and
    # is for explicit local-dev opt-out only.
    scanner: Scanner = "heuristic"
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # ── Document-intelligence engines ────────────────────────────────────────────────────────
    # Primary parser. ``native`` (default) = the built-in PyMuPDF/python-docx/openpyxl/python-pptx
    # adapters; ``docling`` routes PDF/DOCX/PPTX/XLSX through Docling (MIT) for richer layout,
    # reading order and table structure, and falls back to native if Docling isn't installed.
    parser_engine: ParserEngine = "native"
    # OCR engine for scanned pages/images. ``tesseract`` (default) is the bundled best-effort
    # engine; ``paddle`` uses PaddleOCR (Apache-2.0) for stronger multilingual/structured OCR,
    # falling back to Tesseract when PaddleOCR isn't installed.
    ocr_engine: OcrEngine = "tesseract"
    # Apache Tika sidecar (Apache-2.0): universal type-detection / metadata / fallback text for
    # 1,400+ formats. Off unless TIKA_SERVER_URL points at a running Tika server; never the
    # primary parser — a validation/fallback layer only.
    tika_server_url: str | None = None
    # QPDF preflight (Apache-2.0): structural check / repair / linearize / encryption detection
    # before PDF parse, redaction and export. Runs only when the ``qpdf`` binary is present.
    qpdf_preflight: bool = False
    # Ingest pipeline mode. ``sync`` (default) parses/persists in the request, as today. ``async``
    # stages the upload, returns a job_id immediately, and parses off the request path. With
    # ``celery_eager`` (the offline/dev/test default) the "async" work runs inline so no Redis or
    # worker is needed; set CELERY_EAGER=false and run a worker for true off-request execution.
    ingest_mode: IngestMode = "sync"
    celery_eager: bool = True
    # PII detection engine. ``regex`` (default) is the always-present high-precision detector
    # (emails/SSNs/cards/phones/IPs). ``presidio`` additionally runs Microsoft Presidio (MIT) for
    # NER entities (names, locations, dates, …) when it is installed, augmenting — never replacing —
    # the regex hits; falls back to regex-only when Presidio isn't importable.
    pii_engine: PiiEngine = "regex"
    # PDF page rasterization engine for previews. ``pymupdf`` (default) uses PyMuPDF/fitz (AGPL);
    # ``pdfium`` uses pypdfium2 (Apache-2.0/BSD-3) — the permissive migration target. Rendering
    # only; parsing still uses PyMuPDF. Falls back to PyMuPDF if pypdfium2 isn't importable.
    pdf_render_engine: PdfRenderEngine = "pymupdf"
    # Low-level PDF operations engine. ``pymupdf`` (default) = current AGPL behaviour unchanged;
    # ``permissive`` = pypdf+pikepdf for the parity-proven page ops/encryption/compress subset,
    # with PyMuPDF fallback for not-yet-migrated capabilities (watermark/redaction/searchable-PDF).
    pdf_engine: PdfEngine = "pymupdf"

    # Embedded editor providers. ``local``/``basic`` never claim full native fidelity;
    # configure provider URLs to activate real embedded editors.
    office_editor_provider: OfficeEditorProvider = "local"
    onlyoffice_document_server_url: str | None = None
    pdf_editor_provider: PdfEditorProvider = "basic"
    pdf_editor_url: str | None = None

    # ── Gated-capability provider seams ───────────────────────────────────────────────────────
    # Legal e-signature. ``seal`` (default) is the offline integrity seal (tamper-evident, NOT
    # legally binding); ``external`` POSTs to a regulated signing provider when a URL+key are set.
    signature_provider: SignatureProvider = "seal"
    signature_provider_url: str | None = None
    signature_provider_key: str | None = None

    # Cloud IDP. ``local`` (default) uses Tesseract + the deterministic extractor; ``textract`` uses
    # AWS Textract (boto3 + the S3 creds below); ``external`` POSTs pages to a custom IDP endpoint.
    idp_provider: IdpProvider = "local"
    idp_provider_url: str | None = None
    idp_provider_key: str | None = None

    # Handwriting OCR. ``none`` (default) falls back to standard OCR; ``external`` calls a
    # specialized handwriting model over HTTPS.
    handwriting_provider: HandwritingProvider = "none"
    handwriting_provider_url: str | None = None
    handwriting_provider_key: str | None = None

    # Text-to-speech (document → audio). ``none`` (default) returns 501; ``external`` calls a TTS
    # service over HTTPS and streams the audio back.
    tts_provider: TtsProvider = "none"
    tts_provider_url: str | None = None
    tts_provider_key: str | None = None

    # DRM / rights management applied on export. ``none`` (default) → the honest local protection is
    # AES-256 PDF passwording; ``external`` POSTs the export to a DRM service.
    drm_provider: DrmProvider = "none"
    drm_provider_url: str | None = None
    drm_provider_key: str | None = None

    # Real-time presence. ``memory`` (default) is a single-node in-process registry that works out
    # of the box; ``redis`` shares presence across workers/nodes (multi-node seam).
    collab_backend: CollabBackend = "memory"
    collab_redis_url: str | None = None
    # Presence heartbeat TTL (seconds): a viewer drops off this long after their last heartbeat.
    presence_ttl_seconds: int = 20

    # Cloud storage integrations (OAuth). A provider is "connected" only when its client id+secret
    # are set; the shared redirect base builds the OAuth callback URL.
    oauth_redirect_base: str | None = None  # e.g. https://app.example.com
    gdrive_client_id: str | None = None
    gdrive_client_secret: str | None = None
    dropbox_client_id: str | None = None
    dropbox_client_secret: str | None = None
    box_client_id: str | None = None
    box_client_secret: str | None = None
    onedrive_client_id: str | None = None
    onedrive_client_secret: str | None = None
    slack_client_id: str | None = None
    slack_client_secret: str | None = None

    # Stripe billing (optional — checkout returns 501 when unset).
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro: str | None = None
    stripe_price_team: str | None = None
    billing_return_url: str | None = None  # e.g. https://app.example.com/pricing?success=1

    # archive (OOXML/zip) safety limits — defense against zip bombs.
    zip_max_entries: int = 2000
    zip_max_uncompressed_mb: int = 200
    zip_max_ratio: int = 100

    # upload rate limiting (per session, falling back to client IP).
    rate_limit_enabled: bool = True
    rate_limit_uploads_per_min: int = 30
    # rate limit for expensive non-upload operations (clean, redaction-audit, autofill, …).
    rate_limit_ops_per_min: int = 60
    rate_limit_auth_per_min: int = 20
    rate_limit_portal_per_min: int = 120

    # ingestion limits
    max_upload_mb: int = 50
    # Hard cap on pages scanned by per-page analyses (table detection, un-redact test) so a
    # pathological many-page PDF can't exhaust CPU. Content beyond the cap is left as-is.
    max_scan_pages: int = 200
    # Memory-safe production limits (Railway OOM guardrails).
    max_searchable_raster_pages: int = 20  # OCR overlay: raster at most this many PDF pages
    max_searchable_pdf_mb: int = 30  # refuse searchable-PDF when source blob exceeds this
    pdf_raster_scale: float = 1.0  # 1.5 looks nicer but doubles pixmap memory
    pdf_raster_max_side_px: int = 2400  # cap longest raster edge (~letter at ~200dpi)
    max_validation_pdf_pages: int = 80  # redaction proof scan cap on exported PDFs
    max_png_export_lines: int = 450  # PNG writer line cap (~9000px tall)
    allowed_mime_types: str = _CATALOG_MIME_TYPES

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """Railway Postgres URLs use postgresql:// — SQLAlchemy needs postgresql+psycopg://."""
        if isinstance(v, str) and v.startswith("postgresql://") and "+psycopg" not in v:
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def allowed_mimes(self) -> set[str]:
        configured = {m.strip() for m in self.allowed_mime_types.split(",") if m.strip()}
        # Partial ALLOWED_MIME_TYPES env overrides drop formats (e.g. HTML); merge the catalog back.
        if not _CATALOG_MIMES.issubset(configured):
            return configured | _CATALOG_MIMES
        return configured

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "production")

    @property
    def deployed_revision(self) -> str:
        for revision in (
            self.railway_git_commit_sha,
            self.source_commit,
            self.git_commit_sha,
        ):
            if revision and revision.strip():
                return revision.strip()
        return "unknown"

    @property
    def effective_llm_provider(self) -> LLMProvider:
        """The provider actually used at runtime.

        If ``LLM_PROVIDER`` is left at the offline ``noop`` default but an API key is
        present, auto-enable that provider. This means a deploy only needs the key set
        (e.g. ``ANTHROPIC_API_KEY`` on Railway) to turn on AI features — no second
        variable to remember. An explicit non-noop ``llm_provider`` always wins.
        """
        if self.llm_provider != "noop":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "noop"

    @property
    def ai_enabled(self) -> bool:
        """True when a real LLM provider is configured (not the offline noop client)."""
        provider = self.effective_llm_provider
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "anthropic":
            return bool(self.anthropic_api_key)
        return False

    @property
    def office_editor_configured(self) -> bool:
        """True when a real embedded Office editor (OnlyOffice) is wired up."""
        return self.office_editor_provider == "onlyoffice" and bool(
            self.onlyoffice_document_server_url
        )

    @property
    def pdf_editor_configured(self) -> bool:
        """True when a real external PDF editor/SDK is wired up."""
        return self.pdf_editor_provider == "external" and bool(self.pdf_editor_url)

    @property
    def esign_configured(self) -> bool:
        """True when a regulated external e-signature provider is wired up (else integrity seal)."""
        return self.signature_provider == "external" and bool(self.signature_provider_url)

    @property
    def idp_configured(self) -> bool:
        """True when a cloud IDP (Textract/external) is wired up (else: local OCR + extractor)."""
        if self.idp_provider == "textract":
            return bool(self.s3_access_key and self.s3_secret_key)
        if self.idp_provider == "external":
            return bool(self.idp_provider_url)
        return False

    @property
    def handwriting_configured(self) -> bool:
        return self.handwriting_provider == "external" and bool(self.handwriting_provider_url)

    @property
    def tts_configured(self) -> bool:
        return self.tts_provider == "external" and bool(self.tts_provider_url)

    @property
    def drm_configured(self) -> bool:
        return self.drm_provider == "external" and bool(self.drm_provider_url)

    @property
    def tika_configured(self) -> bool:
        """True when an Apache Tika sidecar is reachable for fallback extraction/detection."""
        return bool(self.tika_server_url)

    @property
    def configured_integrations(self) -> list[str]:
        """Cloud providers whose OAuth client id+secret are both set (honest 'connected' list)."""
        pairs = {
            "gdrive": (self.gdrive_client_id, self.gdrive_client_secret),
            "dropbox": (self.dropbox_client_id, self.dropbox_client_secret),
            "box": (self.box_client_id, self.box_client_secret),
            "onedrive": (self.onedrive_client_id, self.onedrive_client_secret),
            "slack": (self.slack_client_id, self.slack_client_secret),
        }
        return [name for name, (cid, secret) in pairs.items() if cid and secret]

    @property
    def billing_configured(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_pro)

    @property
    def database_kind(self) -> str:
        """``sqlite`` or ``postgres`` — surfaced so the UI can flag ephemeral SQLite."""
        return "sqlite" if self.database_url.startswith("sqlite") else "postgres"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def zip_max_uncompressed_bytes(self) -> int:
        return self.zip_max_uncompressed_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
