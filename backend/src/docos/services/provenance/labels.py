"""Sensitivity / policy labels."""

from __future__ import annotations

from sqlalchemy.orm import Session

from docos.db.models import Label


def add_label(session: Session, doc_id: str, label: str) -> None:
    session.add(Label(document_id=doc_id, label=label))
    session.flush()
