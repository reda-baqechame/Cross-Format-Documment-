"""Document ownership authorization — the single chokepoint for per-session isolation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from docos.api.session import Actor
from docos.db.models import (
    Clause,
    Document,
    DocumentShare,
    FillProfile,
    IntegrationToken,
    RenewalReminder,
    SignatureRequest,
    Template,
    WorkflowRecipe,
    WorkflowRun,
)


def owner_clause(session_id_col, user_id_col, actor: Actor):
    """SQLAlchemy filter: owned by session or (when logged in) by user."""
    clauses = [session_id_col == actor.session_id]
    if actor.user_id is not None:
        clauses.append(user_id_col == actor.user_id)
    return or_(*clauses)


def owns(record: Document, actor: Actor) -> bool:
    """True when ``actor`` owns ``record`` via its session or authenticated user."""
    if record.owner_session_id is not None and record.owner_session_id == actor.session_id:
        return True
    if (
        record.owner_user_id is not None
        and actor.user_id is not None
        and record.owner_user_id == actor.user_id
    ):
        return True
    return False


def get_owned_document(session: Session, doc_id: str, actor: Actor) -> Document:
    """Load a document, 404ing if it is missing **or** not owned by ``actor``."""
    record = session.get(Document, doc_id)
    if record is None or not owns(record, actor):
        raise HTTPException(status_code=404, detail="document not found")
    return record


def require_owned(session: Session, doc_id: str, actor: Actor) -> Document:
    """Ownership assertion for routes that don't otherwise need the loaded model."""
    return get_owned_document(session, doc_id, actor)


def claim_session_assets(session: Session, *, from_session: str, to_user: str) -> dict[str, int]:
    """Reassign a session's library assets to a registered user on login/register."""
    counts: dict[str, int] = {}

    def _claim(table, label: str) -> None:
        result = session.execute(
            update(table)
            .where(table.owner_session_id == from_session, table.owner_user_id.is_(None))
            .values(owner_user_id=to_user)
        )
        counts[label] = result.rowcount or 0

    result = session.execute(
        update(Document)
        .where(Document.owner_session_id == from_session, Document.owner_user_id.is_(None))
        .values(owner_user_id=to_user)
    )
    counts["documents"] = result.rowcount or 0
    for table, label in (
        (Template, "templates"),
        (FillProfile, "fill_profiles"),
        (Clause, "clauses"),
        (SignatureRequest, "signature_requests"),
        (IntegrationToken, "integration_tokens"),
        (RenewalReminder, "renewal_reminders"),
        (DocumentShare, "document_shares"),
        (WorkflowRecipe, "workflow_recipes"),
        (WorkflowRun, "workflow_runs"),
    ):
        _claim(table, label)
    return counts


# Backward-compatible alias used in tests.
def claim_documents(session: Session, *, from_session: str, to_user: str) -> int:
    return claim_session_assets(session, from_session=from_session, to_user=to_user)["documents"]


@dataclass(frozen=True)
class ShareAccess:
    share: DocumentShare
    document: Document


def get_valid_share(session: Session, token: str, *, pin: str | None = None) -> ShareAccess:
    """Resolve a portal token to a document; 404 on invalid/expired/revoked shares."""
    share = session.scalar(select(DocumentShare).where(DocumentShare.token == token))
    if share is None or share.revoked:
        raise HTTPException(status_code=404, detail="share link not found")
    if share.expires_at is not None:
        exp = share.expires_at if share.expires_at.tzinfo else share.expires_at.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise HTTPException(status_code=410, detail="share link expired")
    if share.pin_hash is not None:
        from docos.services.auth.passwords import verify_password

        if not pin or not verify_password(pin, share.pin_hash):
            raise HTTPException(status_code=401, detail="invalid PIN")
    document = session.get(Document, share.document_id)
    if document is None or document.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    return ShareAccess(share=share, document=document)
