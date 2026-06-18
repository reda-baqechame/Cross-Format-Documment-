"""Multi-document notebook — ask one question across many documents, with citations.

Like the single-document Q&A in ``routes_query``, answers cite the exact nodes they
draw from — but here citations also carry the source document, and retrieval spans the
whole corpus (or a chosen subset). Deterministic and offline by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_llm_client, get_settings
from docos.services.semantic import corpus as corpus_service

router = APIRouter(prefix="/notebook", tags=["notebook"])


class NotebookRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None  # None ⇒ ask across every document


class NotebookResponse(BaseModel):
    question: str
    answer: str
    citations: list[corpus_service.NotebookCitation]
    used_llm: bool
    document_count: int


@router.post("/ask", response_model=NotebookResponse)
async def notebook_ask(
    body: NotebookRequest, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> NotebookResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")

    docs = load_corpus(session, body.doc_ids, owner_session_id=actor.session_id)
    use_llm = get_settings().llm_provider != "noop"
    result = await corpus_service.notebook_answer(docs, question, get_llm_client(), use_llm=use_llm)
    return NotebookResponse(
        question=question,
        answer=result.answer,
        citations=result.citations,
        used_llm=result.used_llm,
        document_count=len(docs),
    )
