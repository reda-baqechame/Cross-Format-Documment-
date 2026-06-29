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
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_llm_client, get_settings
from docos.services.semantic import corpus as corpus_service
from docos.services.semantic.agents import (
    AgentRun,
    run_corpus_agent,
    run_corpus_agent_loop,
)

router = APIRouter(prefix="/notebook", tags=["notebook"])


class NotebookRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None  # None ⇒ ask across every document


class NotebookAgentRequest(BaseModel):
    goal: str
    doc_ids: list[str] | None = None  # None ⇒ reason across every document


class NotebookResponse(BaseModel):
    question: str
    answer: str
    citations: list[corpus_service.NotebookCitation]
    used_llm: bool
    document_count: int


@router.post("/ask", response_model=NotebookResponse)
async def notebook_ask(
    body: NotebookRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> NotebookResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")

    docs = load_corpus(
        session,
        body.doc_ids,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    use_llm = get_settings().effective_llm_provider != "noop"
    result = await corpus_service.notebook_answer(docs, question, get_llm_client(), use_llm=use_llm)
    return NotebookResponse(
        question=question,
        answer=result.answer,
        citations=result.citations,
        used_llm=result.used_llm,
        document_count=len(docs),
    )


@router.post("/agent", response_model=AgentRun)
async def notebook_agent(
    body: NotebookAgentRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> AgentRun:
    """Run the multi-document agent across the corpus for a goal.

    With an AI provider configured, runs the iterative tool-calling loop (search → observe → cite).
    Offline (``LLM_PROVIDER=noop``) it falls back to a deterministic cross-document analysis. The
    corpus agent is read-only: it cites the document + node for every fact and never mutates.
    """
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="goal is required")
    docs = load_corpus(
        session,
        body.doc_ids,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if get_settings().effective_llm_provider != "noop":
        return await run_corpus_agent_loop(docs, goal, llm=get_llm_client())
    return await run_corpus_agent(docs, goal, get_llm_client())
