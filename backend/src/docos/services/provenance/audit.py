"""Append-only audit log writer."""

from __future__ import annotations

from sqlalchemy.orm import Session

from docos.db.models import AuditEvent


def write_event(
    session: Session,
    doc_id: str | None,
    action: str,
    *,
    actor: str = "system",
    detail: dict | None = None,
) -> None:
    session.add(AuditEvent(document_id=doc_id, action=action, actor=actor, detail=detail or {}))
    session.flush()
