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
    routes_agent,
    routes_approvals,
    routes_auth,
    routes_billing,
    routes_bulk_send,
    routes_capabilities,
    routes_clm,
    routes_comments,
    routes_documents,
    routes_editor,
    routes_esign,
    routes_export,
    routes_forms,
    routes_health,
    routes_health_panel,
    routes_idp,
    routes_integrations,
    routes_jobs,
    routes_library,
    routes_notebook,
    routes_ops_agent,
    routes_packs,
    routes_pages,
    routes_patches,
    routes_presence,
    routes_profile,
    routes_query,
    routes_readiness,
    routes_recipes,
    routes_share,
    routes_suggestions,
    routes_templates,
    routes_tts,
    routes_workflows,
)
from docos.api.observability import (
    RequestContextMiddleware,
    configure_logging,
    init_sentry,
    register_error_handlers,
)
from docos.api.security_headers import SecurityHeadersMiddleware
from docos.api.session import SessionMiddleware
from docos.settings import get_settings

logger = logging.getLogger("docos")

_INSECURE_SIGNING_SECRET = "docos-dev-signing-secret"


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(settings)
    init_sentry(settings)

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
    # Issue/validate the anonymous session cookie so every document gets a private owner.
    app.add_middleware(SessionMiddleware)
    # Defence-in-depth response headers (HSTS only when actually serving over TLS in production).
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    # Outermost: bind a request id + emit access logs for everything below.
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(routes_health.router)
    app.include_router(routes_capabilities.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_billing.router)
    app.include_router(routes_share.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_jobs.router)
    app.include_router(routes_health_panel.router)
    app.include_router(routes_readiness.router)
    app.include_router(routes_patches.router)
    app.include_router(routes_query.router)
    app.include_router(routes_pages.router)
    app.include_router(routes_library.router)
    app.include_router(routes_forms.router)
    app.include_router(routes_profile.router)
    app.include_router(routes_clm.router)
    app.include_router(routes_esign.router)
    app.include_router(routes_integrations.router)
    app.include_router(routes_idp.router)
    app.include_router(routes_tts.router)
    app.include_router(routes_presence.router)
    app.include_router(routes_editor.router)
    app.include_router(routes_export.router)
    app.include_router(routes_comments.router)
    app.include_router(routes_notebook.router)
    app.include_router(routes_ops_agent.router)
    app.include_router(routes_agent.router)
    app.include_router(routes_packs.router)
    app.include_router(routes_approvals.router)
    app.include_router(routes_templates.router)
    app.include_router(routes_suggestions.router)
    app.include_router(routes_bulk_send.router)
    app.include_router(routes_workflows.router)
    app.include_router(routes_recipes.router)
    app.include_router(routes_recipes.tools_router)

    logger.info(
        "docos starting: env=%s privacy_mode=%s blob_backend=%s llm=%s",
        settings.app_env,
        settings.privacy_mode,
        settings.blob_backend,
        settings.effective_llm_provider,
    )
    return app


app = create_app()
