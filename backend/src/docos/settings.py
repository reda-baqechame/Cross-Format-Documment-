"""Application configuration.

Privacy mode and backend choices are config, not code: switching ``PRIVACY_MODE``
or ``BLOB_BACKEND`` swaps concrete service implementations behind the interfaces.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PrivacyMode = Literal["offline", "enterprise", "cloud"]
BlobBackend = Literal["local", "s3"]
LLMProvider = Literal["noop", "openai", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    privacy_mode: PrivacyMode = "offline"
    app_env: Literal["dev", "staging", "production"] = "dev"

    # CORS allow-list for the browser app (comma-separated origins).
    cors_origins: str = "http://localhost:3000"

    # storage
    blob_backend: BlobBackend = "local"
    local_blob_dir: str = "./data/blobs"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "docos"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # infra
    database_url: str = "postgresql+psycopg://docos:docos@localhost:5432/docos"
    redis_url: str = "redis://localhost:6379/0"

    # llm
    llm_provider: LLMProvider = "noop"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # e-signature (HMAC key; override in production via SIGNING_SECRET)
    signing_secret: str = "docos-dev-signing-secret"

    # ingestion limits
    max_upload_mb: int = 50
    allowed_mime_types: str = (
        "text/plain,"
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "application/rtf,"
        "image/png,"
        "image/jpeg,"
        "image/tiff"
    )

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
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
