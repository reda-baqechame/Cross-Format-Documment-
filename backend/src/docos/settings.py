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
Scanner = Literal["noop", "clamav"]
BlobEncryption = Literal["none", "aesgcm"]
OfficeEditorProvider = Literal["local", "onlyoffice"]
PdfEditorProvider = Literal["basic", "external"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    privacy_mode: PrivacyMode = "offline"
    app_env: Literal["dev", "staging", "production"] = "dev"

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

    # e-signature (HMAC key; override in production via SIGNING_SECRET)
    signing_secret: str = "docos-dev-signing-secret"

    # malware scanning. ``noop`` (the offline default) accepts everything; ``clamav`` streams
    # uploads to a clamd daemon and fails closed if it is unreachable.
    scanner: Scanner = "noop"
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # Embedded editor providers. ``local``/``basic`` never claim full native fidelity;
    # configure provider URLs to activate real embedded editors.
    office_editor_provider: OfficeEditorProvider = "local"
    onlyoffice_document_server_url: str | None = None
    pdf_editor_provider: PdfEditorProvider = "basic"
    pdf_editor_url: str | None = None

    # archive (OOXML/zip) safety limits — defense against zip bombs.
    zip_max_entries: int = 2000
    zip_max_uncompressed_mb: int = 200
    zip_max_ratio: int = 100

    # upload rate limiting (per session, falling back to client IP).
    rate_limit_enabled: bool = True
    rate_limit_uploads_per_min: int = 30

    # ingestion limits
    max_upload_mb: int = 50
    allowed_mime_types: str = (
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
        "image/tiff"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """Railway Postgres URLs use postgresql:// — SQLAlchemy needs postgresql+psycopg://."""
        if isinstance(v, str) and v.startswith("postgresql://") and "+psycopg" not in v:
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def allowed_mimes(self) -> set[str]:
        return {m.strip() for m in self.allowed_mime_types.split(",") if m.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "production")

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
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def zip_max_uncompressed_bytes(self) -> int:
        return self.zip_max_uncompressed_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
