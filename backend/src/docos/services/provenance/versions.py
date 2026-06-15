"""Version-graph helpers — each version id is the document's canonical content hash."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.db.models import DocumentVersion
from docos.model.document import CanonicalDocument
from docos.model.serialize import canonical_hash, to_dict


def commit(
    session: Session, doc: CanonicalDocument, *, parent_id: str | None, patch_id: str | None
) -> str:
    version_id = canonical_hash(doc)
    doc.content_hash = version_id
    existing = session.get(DocumentVersion, version_id)
    if existing is None:
        session.add(
            DocumentVersion(
                id=version_id,
                document_id=doc.doc_id,
                parent_id=parent_id,
                model=to_dict(doc),
                patch_id=patch_id,
            )
        )
        session.flush()
    return version_id


def lineage(session: Session, doc_id: str) -> list[DocumentVersion]:
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.created_at)
    )
    return list(session.execute(stmt).scalars())
