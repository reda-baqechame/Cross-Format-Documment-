"""Liveness/readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from docos.api.schemas import HealthCheck
from docos.deps import db_session, settings_dep
from docos.settings import Settings

router = APIRouter(tags=["system"])


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
    )
