"""FastAPI application factory.

Mounts the routers that expose the canonical model and the five services. The
resulting OpenAPI schema is the contract consumed by the frontend via codegen.
Configuration (CORS, environment, secrets) comes from :mod:`docos.settings`, so the
same image runs unchanged across dev, staging, and production.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docos.api import (
    routes_documents,
    routes_export,
    routes_forms,
    routes_health,
    routes_health_panel,
    routes_library,
    routes_pages,
    routes_patches,
    routes_query,
)
from docos.settings import get_settings

logger = logging.getLogger("docos")

_INSECURE_SIGNING_SECRET = "docos-dev-signing-secret"


def create_app() -> FastAPI:
    settings = get_settings()

    # Fail fast on insecure production config rather than silently shipping a known key.
    if settings.is_production and settings.signing_secret == _INSECURE_SIGNING_SECRET:
        raise RuntimeError(
            "SIGNING_SECRET must be overridden in staging/production "
            "(the default development key is insecure)."
        )

    app = FastAPI(
        title="Cross-Format Document OS",
        version="0.1.0",
        description="Open, edit, convert, and run trust operations on any document.",
        docs_url=None if settings.is_production else "/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_health.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_health_panel.router)
    app.include_router(routes_patches.router)
    app.include_router(routes_query.router)
    app.include_router(routes_pages.router)
    app.include_router(routes_library.router)
    app.include_router(routes_forms.router)
    app.include_router(routes_export.router)

    logger.info(
        "docos starting: env=%s privacy_mode=%s blob_backend=%s llm=%s",
        settings.app_env,
        settings.privacy_mode,
        settings.blob_backend,
        settings.llm_provider,
    )
    return app


app = create_app()
