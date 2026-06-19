"""Read-only document intelligence — ask questions and summarize, with citations.

These endpoints never mutate the document, so they don't commit a version. They run
over the canonical model, so one implementation serves every format. Answers are
deterministic and fully offline with ``LLM_PROVIDER=noop``; a configured provider is
used only to phrase the same cited excerpts more fluently.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    AskRequest,
    AskResponse,
    AutopilotResponse,
    ClassifyResponse,
    DiffResponse,
    ExtractResponse,
    IntelligenceResponse,
    SummaryResponse,
    TranslateRequest,
    TranslateResponse,
)
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_llm_client, get_settings
from docos.services.provenance import diff
from docos.services.semantic import classify as classify_service
from docos.services.semantic import extract as extract_service
from docos.services.semantic import intelligence, reader
from docos.services.semantic.skills import autopilot as autopilot_service

router = APIRouter(prefix="/documents", tags=["query"])


@router.post("/{doc_id}/ask", response_model=AskResponse)
async def ask_document(
    doc_id: str,
    body: AskRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> AskResponse:
    """Answer a question from the document's own text, citing the nodes used."""
    _record, doc = _load_latest(session, doc_id, actor)
    use_llm = get_settings().effective_llm_provider != "noop"
    result = await reader.answer(doc, body.question, get_llm_client(), use_llm=use_llm)
    return AskResponse(
        doc_id=doc_id,
        answer=result.answer,
        citations=result.citations,
        used_llm=result.used_llm,
    )


@router.get("/{doc_id}/summary", response_model=SummaryResponse)
async def summarize_document(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> SummaryResponse:
    """Summarize the document, citing the nodes the summary draws from."""
    _record, doc = _load_latest(session, doc_id, actor)
    use_llm = get_settings().effective_llm_provider != "noop"
    result = await reader.summarize(doc, get_llm_client(), use_llm=use_llm)
    return SummaryResponse(
        doc_id=doc_id,
        summary=result.summary,
        citations=result.citations,
        used_llm=result.used_llm,
    )


@router.get("/{doc_id}/diff", response_model=DiffResponse)
def diff_documents(
    doc_id: str,
    against: str = Query(..., description="the other document id to compare against"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> DiffResponse:
    """Block-level redline between this document and another (cross-format)."""
    _record, base = _load_latest(session, doc_id, actor)
    _other_record, other = _load_latest(session, against, actor)
    return DiffResponse(doc_id=doc_id, against=against, result=diff.diff_documents(base, other))


@router.get("/{doc_id}/extract", response_model=ExtractResponse)
def extract_document(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> ExtractResponse:
    """Pull entities (dates/money/emails/…) and Label:value fields, with provenance."""
    _record, doc = _load_latest(session, doc_id, actor)
    return ExtractResponse(doc_id=doc_id, extraction=extract_service.extract(doc))


@router.get("/{doc_id}/classify", response_model=ClassifyResponse)
def classify_document(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> ClassifyResponse:
    """Detect the document type (invoice/contract/resume/…) with explainable signals."""
    _record, doc = _load_latest(session, doc_id, actor)
    return ClassifyResponse(doc_id=doc_id, classification=classify_service.classify(doc))


@router.get("/{doc_id}/intelligence", response_model=IntelligenceResponse)
def document_intelligence(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> IntelligenceResponse:
    """Typed read for the detected document kind: the fields that matter plus
    actionable checks (totals reconcile, missing clauses, ATS/contact gaps)."""
    _record, doc = _load_latest(session, doc_id, actor)
    return IntelligenceResponse(doc_id=doc_id, insight=intelligence.analyze(doc))


@router.get("/{doc_id}/autopilot", response_model=AutopilotResponse)
def autopilot(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> AutopilotResponse:
    """Document Autopilot: detect the document's purpose, extract its key fields, run checks,
    and recommend next actions — the typed-object view of the document. Deterministic/offline."""
    _record, doc = _load_latest(session, doc_id, actor)
    return AutopilotResponse(doc_id=doc_id, autopilot=autopilot_service.analyze(doc))


@router.post("/{doc_id}/translate", response_model=TranslateResponse)
async def translate_document(
    doc_id: str,
    body: TranslateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> TranslateResponse:
    """Translate the document text. Requires a configured LLM provider."""
    if get_settings().effective_llm_provider == "noop":
        raise HTTPException(
            status_code=501,
            detail="translation requires an LLM provider — set ANTHROPIC_API_KEY or OPENAI_API_KEY",
        )
    _record, doc = _load_latest(session, doc_id, actor)
    text = await reader.translate(doc, body.target_language, get_llm_client())
    return TranslateResponse(
        doc_id=doc_id, target_language=body.target_language, translated_text=text
    )
