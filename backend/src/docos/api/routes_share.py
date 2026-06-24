"""Shareable client portal links — token-gated document access."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document, get_valid_share, owner_clause
from docos.api.schemas import DocumentModelResponse, ReadinessResponse
from docos.api.session import Actor, get_actor
from docos.db.models import DocumentShare, DocumentVersion
from docos.deps import db_session, get_provenance
from docos.model.serialize import from_dict
from docos.services.auth.passwords import hash_password
from docos.services.billing.plans import require_portal_access
from docos.services.provenance import readiness

router = APIRouter(tags=["share"])


class CreateShareRequest(BaseModel):
    permission: str = "view"  # view|comment|sign
    expires_in_days: int | None = 30
    pin: str | None = None
    recipient_label: str | None = None


class ShareView(BaseModel):
    id: str
    token: str
    document_id: str
    permission: str
    recipient_label: str | None
    expires_at: datetime | None
    portal_url: str
    revoked: bool


class ShareListResponse(BaseModel):
    doc_id: str
    shares: list[ShareView]


def _portal_path(token: str) -> str:
    return f"/portal/{token}"


def _share_view(share: DocumentShare) -> ShareView:
    return ShareView(
        id=share.id,
        token=share.token,
        document_id=share.document_id,
        permission=share.permission,
        recipient_label=share.recipient_label,
        expires_at=share.expires_at,
        portal_url=_portal_path(share.token),
        revoked=share.revoked,
    )


@router.post("/documents/{doc_id}/shares", response_model=ShareView)
def create_share(
    doc_id: str,
    body: CreateShareRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> ShareView:
    require_portal_access(session, actor)
    get_owned_document(session, doc_id, actor)
    if body.permission not in ("view", "comment", "sign"):
        raise HTTPException(status_code=422, detail="permission must be view, comment, or sign")
    expires_at = None
    if body.expires_in_days is not None and body.expires_in_days > 0:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)
    token = secrets.token_urlsafe(24)
    share = DocumentShare(
        id=f"share_{uuid.uuid4().hex[:16]}",
        document_id=doc_id,
        token=token,
        permission=body.permission,
        pin_hash=hash_password(body.pin) if body.pin else None,
        recipient_label=body.recipient_label,
        expires_at=expires_at,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    session.add(share)
    get_provenance(session).record_event(
        doc_id,
        "share.created",
        actor=actor.user_id or actor.session_id,
        detail={"share_id": share.id, "permission": body.permission},
    )
    session.commit()
    return _share_view(share)


@router.get("/documents/{doc_id}/shares", response_model=ShareListResponse)
def list_shares(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> ShareListResponse:
    get_owned_document(session, doc_id, actor)
    rows = session.scalars(
        select(DocumentShare)
        .where(
            DocumentShare.document_id == doc_id,
            owner_clause(DocumentShare.owner_session_id, DocumentShare.owner_user_id, actor),
        )
        .order_by(DocumentShare.created_at.desc())
    ).all()
    return ShareListResponse(doc_id=doc_id, shares=[_share_view(s) for s in rows])


@router.delete("/documents/{doc_id}/shares/{share_id}")
def revoke_share(
    doc_id: str,
    share_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> dict[str, bool]:
    get_owned_document(session, doc_id, actor)
    share = session.get(DocumentShare, share_id)
    if share is None or share.document_id != doc_id:
        raise HTTPException(status_code=404, detail="share not found")
    share.revoked = True
    session.commit()
    return {"ok": True}


@router.get("/portal/{token}", response_model=ShareView)
def portal_info(
    token: str,
    pin: str | None = Query(default=None),
    session: Session = Depends(db_session),
) -> ShareView:
    access = get_valid_share(session, token, pin=pin)
    return _share_view(access.share)


@router.get("/portal/{token}/model", response_model=DocumentModelResponse)
def portal_model(
    token: str,
    pin: str | None = Query(default=None),
    session: Session = Depends(db_session),
) -> DocumentModelResponse:
    access = get_valid_share(session, token, pin=pin)
    version = session.get(DocumentVersion, access.document.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentModelResponse(document=from_dict(version.model), version_id=version.id)


@router.get("/portal/{token}/readiness", response_model=ReadinessResponse)
def portal_readiness(
    token: str,
    pin: str | None = Query(default=None),
    session: Session = Depends(db_session),
) -> ReadinessResponse:
    access = get_valid_share(session, token, pin=pin)
    version = session.get(DocumentVersion, access.document.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="document not found")
    doc = from_dict(version.model)
    report = readiness.build_report(doc)
    return ReadinessResponse(doc_id=access.document.id, report=report)


def create_recipient_share(
    session: Session,
    *,
    doc_id: str,
    actor: Actor,
    recipient: str,
    permission: str = "sign",
) -> DocumentShare:
    """Used by bulk-send to mint a portal link per recipient."""
    token = secrets.token_urlsafe(24)
    share = DocumentShare(
        id=f"share_{uuid.uuid4().hex[:16]}",
        document_id=doc_id,
        token=token,
        permission=permission,
        recipient_label=recipient,
        expires_at=datetime.now(UTC) + timedelta(days=90),
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    session.add(share)
    return share
