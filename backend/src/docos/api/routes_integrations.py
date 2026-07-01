"""Cloud-storage integrations (gated OAuth seam).

Lists providers and their honest state, runs the OAuth authorization-code handshake when the
provider's client credentials are configured, stores the session-scoped token, and imports a file
through the **same** ingest pipeline as a direct upload. Without credentials every provider reads as
not-connected and ``connect`` returns 501.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.access import owner_clause
from docos.api.ratelimit import enforce_op_rate, enforce_upload_rate
from docos.api.routes_documents import ingest_bytes
from docos.api.schemas import (
    ConnectResponse,
    IntegrationImportRequest,
    IntegrationListResponse,
    IntegrationStatus,
    UploadResponse,
)
from docos.api.session import Actor, get_actor
from docos.db.models import IntegrationToken
from docos.deps import (
    blob_store_dep,
    db_session,
    get_ingestion_gateway,
    get_registry,
)
from docos.services import integrations
from docos.services.auth.secret_store import seal, unseal
from docos.services.docengine.registry import AdapterRegistry
from docos.services.ingestion.interface import IngestionGateway
from docos.settings import get_settings
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _sign_state(session_id: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{session_id}.{mac}"


def _valid_state(state: str, session_id: str, secret: str) -> bool:
    return hmac.compare_digest(state, _sign_state(session_id, secret))


def _token_for(session: Session, actor: Actor, name: str) -> IntegrationToken | None:
    return (
        session.execute(
            select(IntegrationToken).where(
                IntegrationToken.provider == name,
                owner_clause(
                    IntegrationToken.owner_session_id,
                    IntegrationToken.owner_user_id,
                    actor,
                ),
            )
        )
        .scalars()
        .first()
    )


@router.get("", response_model=IntegrationListResponse)
def list_integrations(
    session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> IntegrationListResponse:
    settings = get_settings()
    out: list[IntegrationStatus] = []
    for name in integrations.provider_names():
        spec = integrations.get_spec(name)
        out.append(
            IntegrationStatus(
                name=name,
                label=spec.label if spec else name,
                configured=integrations.is_configured(settings, name),
                connected=_token_for(session, actor, name) is not None,
            )
        )
    return IntegrationListResponse(integrations=out)


@router.get("/{name}/connect", response_model=ConnectResponse)
def connect(name: str, actor: Actor = Depends(get_actor)) -> ConnectResponse:
    settings = get_settings()
    if integrations.get_spec(name) is None:
        raise HTTPException(status_code=404, detail="unknown integration")
    if not integrations.is_configured(settings, name):
        raise HTTPException(
            status_code=501,
            detail=f"{name} is not configured — set {name.upper()}_CLIENT_ID/SECRET + "
            "OAUTH_REDIRECT_BASE to enable it.",
        )
    state = _sign_state(actor.session_id, settings.signing_secret)
    return ConnectResponse(authorize_url=integrations.authorize_url(settings, name, state=state))


@router.get("/{name}/callback")
def callback(
    name: str,
    code: str = Query(...),
    state: str = Query(...),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RedirectResponse:
    settings = get_settings()
    if not integrations.is_configured(settings, name):
        raise HTTPException(status_code=501, detail=f"{name} is not configured")
    if not _valid_state(state, actor.session_id, settings.signing_secret):
        raise HTTPException(status_code=400, detail="invalid OAuth state")
    try:
        tokens = integrations.exchange_code(settings, name, code)
    except Exception as exc:  # noqa: BLE001 - surface a clean error
        raise HTTPException(status_code=502, detail=f"token exchange failed: {exc}") from exc

    row = _token_for(session, actor, name) or IntegrationToken(
        id=f"itok_{uuid.uuid4().hex[:16]}",
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        provider=name,
        access_token="",
    )
    context = f"integration:{row.id}:{name}"
    row.access_token = (
        seal(str(tokens.get("access_token", "")), secret=settings.signing_secret, context=context)
        or ""
    )
    row.refresh_token = seal(
        tokens.get("refresh_token"), secret=settings.signing_secret, context=context
    )
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    # Back to the app; the home page reads /integrations to reflect the connected state.
    return RedirectResponse(url="/?connected=" + name, status_code=303)


@router.delete("/{name}", status_code=204)
def disconnect(
    name: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> None:
    row = _token_for(session, actor, name)
    if row is not None:
        session.delete(row)
        session.commit()


@router.post("/{name}/import", response_model=UploadResponse)
async def import_file(
    name: str,
    body: IntegrationImportRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_upload_rate),
    _op: None = Depends(enforce_op_rate),
) -> UploadResponse:
    """Download a file from the connected provider and ingest it like any upload."""
    if integrations.get_spec(name) is None:
        raise HTTPException(status_code=404, detail="unknown integration")
    token = _token_for(session, actor, name)
    if token is None:
        raise HTTPException(status_code=401, detail=f"{name} is not connected")
    try:
        settings = get_settings()
        access_token = unseal(
            token.access_token,
            secret=settings.signing_secret,
            context=f"integration:{token.id}:{name}",
        )
        if not access_token:
            raise ValueError("stored provider credential is empty")
        data = integrations.download(name, body.file_url, access_token, gateway.max_bytes)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"download failed: {exc}") from exc
    record, version_id, detected = await ingest_bytes(
        session,
        filename=body.filename or "import",
        data=data,
        actor=actor,
        gateway=gateway,
        registry=registry,
        blob_store=blob_store,
    )
    return UploadResponse(doc_id=record.id, version_id=version_id, detected_format=detected)
