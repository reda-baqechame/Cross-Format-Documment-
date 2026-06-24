"""Load the current canonical model of many documents — the corpus for cross-document
semantic search and the multi-document notebook."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.db.models import Document, DocumentVersion
from docos.model.serialize import from_dict
from docos.services.semantic.corpus import CorpusDoc


def load_corpus(
    session: Session,
    doc_ids: list[str] | None = None,
    *,
    owner_session_id: str | None = None,
    owner_user_id: str | None = None,
) -> list[CorpusDoc]:
    """Every document's current model (newest first), optionally filtered to ``doc_ids``.

    When ``owner_session_id`` / ``owner_user_id`` are given, only that owner's documents load.
    """
    from sqlalchemy import or_

    wanted = set(doc_ids) if doc_ids else None
    stmt = select(Document)
    if owner_session_id is not None or owner_user_id is not None:
        clauses = []
        if owner_session_id is not None:
            clauses.append(Document.owner_session_id == owner_session_id)
        if owner_user_id is not None:
            clauses.append(Document.owner_user_id == owner_user_id)
        stmt = stmt.where(or_(*clauses))
    records = session.scalars(stmt.order_by(Document.created_at.desc())).all()
    corpus: list[CorpusDoc] = []
    for record in records:
        if wanted is not None and record.id not in wanted:
            continue
        if record.current_version_id is None:
            continue
        version = session.get(DocumentVersion, record.current_version_id)
        if version is None:
            continue
        corpus.append(CorpusDoc(doc_id=record.id, title=record.title, doc=from_dict(version.model)))
    return corpus
