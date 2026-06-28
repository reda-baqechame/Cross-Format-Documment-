"""Dependency-injection providers.

Privacy mode and backend settings decide which concrete implementations are wired
behind each interface. Routes depend on these providers, never on concrete classes.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session

from docos.db.base import get_session
from docos.services.docengine.registry import AdapterRegistry, default_registry
from docos.services.ingestion.gateway import IngestionGatewayImpl
from docos.services.ingestion.interface import IngestionGateway
from docos.services.ingestion.scanner import (
    ClamAVScanner,
    CompositeScanner,
    ContentDefenseScanner,
    MalwareScanner,
    NoopScanner,
)
from docos.services.provenance.service import ProvenancePolicyServiceImpl
from docos.services.semantic.llm.base import LLMClient
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl
from docos.settings import Settings, get_settings
from docos.storage.blob import BlobStore
from docos.storage.local import LocalBlobStore
from docos.storage.s3 import S3BlobStore


@lru_cache
def get_blob_store() -> BlobStore:
    s = get_settings()
    base: BlobStore
    if s.blob_backend == "s3":
        base = S3BlobStore(
            bucket=s.s3_bucket,
            endpoint_url=s.s3_endpoint_url,
            access_key=s.s3_access_key,
            secret_key=s.s3_secret_key,
        )
    else:
        base = LocalBlobStore(s.local_blob_dir)
    if s.blob_encryption == "aesgcm":
        from docos.storage.encrypted import EncryptingBlobStore, derive_key

        return EncryptingBlobStore(base, derive_key(s.blob_encryption_key or s.signing_secret))
    return base


def blob_store_dep() -> BlobStore:
    """FastAPI provider wrapping :func:`get_blob_store` (overridable in tests)."""
    return get_blob_store()


@lru_cache
def get_registry() -> AdapterRegistry:
    return default_registry(get_settings().parser_engine)


def get_ocr_service():
    """The configured OCR engine (Tesseract by default; PaddleOCR when set up and installed)."""
    from docos.services.ocr.factory import get_ocr_service as _factory

    return _factory()


def get_tika_client():
    """An Apache Tika fallback/validation client, or ``None`` when no Tika server is configured."""
    s = get_settings()
    if not s.tika_configured:
        return None
    from docos.services.ingestion.tika import TikaClient

    return TikaClient(s.tika_server_url or "")


@lru_cache
def get_llm_client() -> LLMClient:
    s = get_settings()
    provider = s.effective_llm_provider
    if provider == "openai":
        from docos.services.semantic.llm.openai import OpenAIClient

        return OpenAIClient(s.openai_api_key)
    if provider == "anthropic":
        from docos.services.semantic.llm.anthropic import AnthropicClient

        if s.llm_model:
            return AnthropicClient(s.anthropic_api_key, model=s.llm_model)
        return AnthropicClient(s.anthropic_api_key)
    return LocalNoopClient()


def get_ingestion_gateway() -> IngestionGateway:
    s = get_settings()
    scanner: MalwareScanner
    if s.scanner == "clamav":
        # Layer the always-on offline content-defense in front of signature AV.
        scanner = CompositeScanner(
            [ContentDefenseScanner(), ClamAVScanner(host=s.clamav_host, port=s.clamav_port)]
        )
    elif s.scanner == "noop":
        scanner = NoopScanner()
    else:  # "heuristic" (default)
        scanner = ContentDefenseScanner()
    return IngestionGatewayImpl(
        blob_store=get_blob_store(),
        allowed_mimes=s.allowed_mimes,
        max_bytes=s.max_upload_bytes,
        scanner=scanner,
        fail_closed=s.scanner != "noop",
        zip_max_entries=s.zip_max_entries,
        zip_max_uncompressed=s.zip_max_uncompressed_bytes,
        zip_max_ratio=s.zip_max_ratio,
    )


def get_orchestrator() -> SemanticOrchestratorImpl:
    return SemanticOrchestratorImpl(get_llm_client())


def get_signature_provider():
    """The e-signature provider: external when configured, else the honest integrity seal."""
    from docos.services.esign import ExternalSignatureProvider, SealProvider

    s = get_settings()
    if s.esign_configured:
        return ExternalSignatureProvider(s.signature_provider_url, s.signature_provider_key)
    return SealProvider()


def get_idp_provider():
    """The cloud IDP provider, or None when only local extraction is available."""
    s = get_settings()
    if not s.idp_configured:
        return None
    if s.idp_provider == "textract":
        from docos.services.ocr.idp import TextractIdp

        return TextractIdp(s.s3_access_key, s.s3_secret_key, s.s3_endpoint_url and None)
    from docos.services.ocr.idp import ExternalIdp

    return ExternalIdp(s.idp_provider_url, s.idp_provider_key)


def get_handwriting_provider():
    """The handwriting-OCR provider, or None when not configured."""
    s = get_settings()
    if not s.handwriting_configured:
        return None
    from docos.services.ocr.handwriting import ExternalHandwriting

    return ExternalHandwriting(s.handwriting_provider_url, s.handwriting_provider_key)


def get_tts_provider():
    """The TTS provider: external when configured, else a noop that signals 'not configured'."""
    from docos.services.tts import ExternalTts, NoopTts

    s = get_settings()
    if s.tts_configured:
        return ExternalTts(s.tts_provider_url, s.tts_provider_key)
    return NoopTts()


def get_drm_provider():
    """The DRM provider, or None when not configured (local protection = AES-256 PDF password)."""
    s = get_settings()
    if not s.drm_configured:
        return None
    from docos.services.drm import ExternalDrm

    return ExternalDrm(s.drm_provider_url, s.drm_provider_key)


@lru_cache
def get_presence_hub():
    """Process-wide presence registry (single-node in-process; Redis is the multi-node seam)."""
    from docos.services.collab.presence import MemoryHub

    return MemoryHub(ttl_seconds=get_settings().presence_ttl_seconds)


def get_provenance(session: Session) -> ProvenancePolicyServiceImpl:
    return ProvenancePolicyServiceImpl(session)


# Re-export the DB session dependency for routers.
def db_session() -> Iterator[Session]:
    yield from get_session()


def settings_dep() -> Settings:
    return get_settings()
