"""Liveness/readiness endpoints.

``/live``  — the process is up. No dependencies; never fails while the app can answer.
``/ready`` — the app can actually serve document operations: required tables exist, blob
             storage is writable, and migrations are applied. Returns 503 otherwise so a
             broken deploy (e.g. a Railway container with no volume at ``/app/data``) is not
             reported as healthy. Railway's healthcheck points here.
``/health``— legacy summary the frontend reads for provider/storage status; always 200.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from docos.api.schemas import HealthCheck, ReadyCheck
from docos.deps import blob_store_dep, db_session, settings_dep
from docos.settings import Settings
from docos.storage.blob import BlobStore

router = APIRouter(tags=["system"])


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness: the process is running. Used to restart hung containers, not to gate traffic."""
    return {"status": "alive"}


@router.get("/health", response_model=HealthCheck)
def health(
    session: Session = Depends(db_session), settings: Settings = Depends(settings_dep)
) -> HealthCheck:
    try:
        session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # pragma: no cover - depends on live db
        db_status = f"error: {exc}"
    return HealthCheck(
        status="ok",
        privacy_mode=settings.privacy_mode,
        blob_backend=settings.blob_backend,
        db=db_status,
        ai_enabled=settings.ai_enabled,
        llm_provider=settings.effective_llm_provider,
        office_editor=settings.office_editor_configured,
        pdf_editor=settings.pdf_editor_configured,
        database=settings.database_kind,
        esign_configured=settings.esign_configured,
        idp_configured=settings.idp_configured,
        handwriting_configured=settings.handwriting_configured,
        tts_configured=settings.tts_configured,
        drm_configured=settings.drm_configured,
        cloud_integrations=settings.configured_integrations,
        billing_configured=settings.billing_configured,
    )


@router.get("/ready", response_model=ReadyCheck)
async def ready(
    response: Response,
    session: Session = Depends(db_session),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> ReadyCheck:
    """Deep readiness: required tables exist and blob storage is writable.

    Readiness gates on the things that actually block serving documents — the core tables existing
    (which is the real proof migrations ran) and writable blob storage. The Alembic revision is
    reported for visibility but is informational: a schema created without an Alembic stamp (e.g.
    metadata create_all) is still serviceable, so it does not flip readiness on its own.
    """
    checks: dict[str, str] = {}
    gates: list[bool] = []

    # Core tables must exist (proves migrations created the schema, not just that the DB opens).
    for table in ("documents", "document_versions"):
        try:
            session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
            checks[f"table:{table}"] = "ok"
            gates.append(True)
        except Exception as exc:  # pragma: no cover - depends on live db
            checks[f"table:{table}"] = f"error: {exc}"
            gates.append(False)

    # Blob storage is writable — write then delete a throwaway probe object.
    probe_key = f"_healthz/{uuid.uuid4().hex}"
    try:
        await blob_store.put(probe_key, b"ok")
        await blob_store.delete(probe_key)
        checks["blob_storage"] = "ok"
        gates.append(True)
    except Exception as exc:  # pragma: no cover - depends on live storage
        checks["blob_storage"] = f"error: {exc}"
        gates.append(False)

    # Informational: which Alembic revision (if any) is stamped.
    try:
        rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["migrations"] = f"at {rev}" if rev else "no revision stamped"
    except Exception:  # noqa: BLE001 - no alembic_version table (e.g. create_all) is not fatal
        checks["migrations"] = "no alembic stamp"

    ok = all(gates)
    if not ok:
        response.status_code = 503
    return ReadyCheck(ok=ok, checks=checks)
