"""FastAPI application factory.

Mounts the routers that expose the canonical model and the five services. The
resulting OpenAPI schema is the contract consumed by the frontend via codegen.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docos.api import (
    routes_documents,
    routes_export,
    routes_health,
    routes_health_panel,
    routes_patches,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cross-Format Document OS",
        version="0.1.0",
        description="Open, edit, convert, and run trust operations on any document.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_health.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_health_panel.router)
    app.include_router(routes_patches.router)
    app.include_router(routes_export.router)
    return app


app = create_app()
