"""Library — organize (tags) and find (full-text search) across all documents.

Tags reuse the ``Label`` table. Search scans each document's current canonical model, so
it works across every format with one implementation. (It loads models on demand — fine
at this scale; a dedicated text index is the next step for large corpora.)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.schemas import (
    SearchHit,
    SearchResponse,
    TagRequest,
    TagsResponse,
)
from docos.db.models import Document, DocumentVersion, Label
from docos.deps import db_session
from docos.model.serialize import from_dict
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.semantic import corpus as corpus_service

router = APIRouter(tags=["library"])


def _tags(session: Session, doc_id: str) -> list[str]:
    rows = session.scalars(select(Label).where(Label.document_id == doc_id)).all()
    return sorted({r.label for r in rows})


@router.get("/documents/{doc_id}/tags", response_model=TagsResponse)
def list_tags(doc_id: str, session: Session = Depends(db_session)) -> TagsResponse:
    if session.get(Document, doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return TagsResponse(doc_id=doc_id, tags=_tags(session, doc_id))


@router.post("/documents/{doc_id}/tags", response_model=TagsResponse)
def add_tag(
    doc_id: str, body: TagRequest, session: Session = Depends(db_session)
) -> TagsResponse:
    if session.get(Document, doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    tag = body.tag.strip()
    if tag and tag not in _tags(session, doc_id):
        session.add(Label(document_id=doc_id, label=tag))
        session.commit()
    return TagsResponse(doc_id=doc_id, tags=_tags(session, doc_id))


@router.delete("/documents/{doc_id}/tags/{tag}", response_model=TagsResponse)
def remove_tag(doc_id: str, tag: str, session: Session = Depends(db_session)) -> TagsResponse:
    rows = session.scalars(
        select(Label).where(Label.document_id == doc_id, Label.label == tag)
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()
    return TagsResponse(doc_id=doc_id, tags=_tags(session, doc_id))


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    session: Session = Depends(db_session),
    limit: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    """Full-text search across every document's current content (redaction-aware)."""
    needle = q.lower()
    hits: list[SearchHit] = []
    records = session.scalars(select(Document).order_by(Document.created_at.desc())).all()
    for record in records:
        if record.current_version_id is None:
            continue
        version = session.get(DocumentVersion, record.current_version_id)
        if version is None:
            continue
        doc = from_dict(version.model)
        for node in doc.walk():
            text = getattr(node, "text", "")
            if text and not is_redacted(doc, node.id):
                pos = text.lower().find(needle)
                if pos != -1:
                    start = max(0, pos - 40)
                    snippet = ("…" if start else "") + text[start : pos + len(q) + 40].strip() + "…"
                    hits.append(SearchHit(doc_id=record.id, title=record.title, snippet=snippet))
                    break
        if len(hits) >= limit:
            break
    return SearchResponse(query=q, hits=hits)


@router.get("/search/semantic", response_model=list[corpus_service.SemanticHit])
def semantic_search(
    q: str = Query(..., min_length=1),
    session: Session = Depends(db_session),
    limit: int = Query(20, ge=1, le=100),
) -> list[corpus_service.SemanticHit]:
    """Relevance-ranked search across the corpus (TF-IDF cosine; offline, deterministic).

    Unlike substring ``/search``, this ranks whole documents by semantic relevance, so a
    query matches documents that discuss the topic even without the exact word.
    """
    return corpus_service.semantic_search(load_corpus(session), q, limit=limit)
