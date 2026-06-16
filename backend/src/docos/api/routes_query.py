"""Read-only document intelligence — ask questions and summarize, with citations.

These endpoints never mutate the document, so they don't commit a version. They run
over the canonical model, so one implementation serves every format. Answers are
deterministic and fully offline with ``LLM_PROVIDER=noop``; a configured provider is
used only to phrase the same cited excerpts more fluently.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import AskRequest, AskResponse, SummaryResponse
from docos.deps import db_session, get_llm_client, get_settings
from docos.services.semantic import reader

router = APIRouter(prefix="/documents", tags=["query"])


@router.post("/{doc_id}/ask", response_model=AskResponse)
async def ask_document(
    doc_id: str, body: AskRequest, session: Session = Depends(db_session)
) -> AskResponse:
    """Answer a question from the document's own text, citing the nodes used."""
    _record, doc = _load_latest(session, doc_id)
    use_llm = get_settings().llm_provider != "noop"
    result = await reader.answer(doc, body.question, get_llm_client(), use_llm=use_llm)
    return AskResponse(
        doc_id=doc_id,
        answer=result.answer,
        citations=result.citations,
        used_llm=result.used_llm,
    )


@router.get("/{doc_id}/summary", response_model=SummaryResponse)
async def summarize_document(
    doc_id: str, session: Session = Depends(db_session)
) -> SummaryResponse:
    """Summarize the document, citing the nodes the summary draws from."""
    _record, doc = _load_latest(session, doc_id)
    use_llm = get_settings().llm_provider != "noop"
    result = await reader.summarize(doc, get_llm_client(), use_llm=use_llm)
    return SummaryResponse(
        doc_id=doc_id,
        summary=result.summary,
        citations=result.citations,
        used_llm=result.used_llm,
    )
