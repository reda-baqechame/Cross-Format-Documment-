"""Document ownership authorization — the single chokepoint for per-session isolation.

Every document-scoped route resolves the request :class:`Actor` and loads the document
through :func:`get_owned_document`, which raises **404** (never 403 — a 403 would leak that
the id exists) when the document isn't owned by the caller. Centralizing the check here keeps
authorization out of individual handlers, so a new route is safe by construction as long as it
loads documents this way.

Future auth seam: ``Document.owner_user_id`` lets a registered user *claim* the documents
created under their anonymous session (:func:`claim_documents`); :func:`owns` already honors
both the session and the user, so claimed documents stay visible to both.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from docos.api.session import Actor
from docos.db.models import Document


def owns(record: Document, actor: Actor) -> bool:
    """True when ``actor`` owns ``record`` via its session or (future) authenticated user."""
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


def claim_documents(session: Session, *, from_session: str, to_user: str) -> int:
    """Seam (not yet exposed): reassign a session's documents to a now-registered user."""
    result = session.execute(
        update(Document)
        .where(Document.owner_session_id == from_session, Document.owner_user_id.is_(None))
        .values(owner_user_id=to_user)
    )
    return result.rowcount or 0
