"""Guided business document workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowPreviewRequest,
    WorkflowPreviewResponse,
)
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_provenance
from docos.services.workflows import execute_workflow, preview_workflow

router = APIRouter(prefix="/documents", tags=["workflows"])


@router.post("/{doc_id}/workflows/preview", response_model=WorkflowPreviewResponse)
def preview(
    doc_id: str,
    body: WorkflowPreviewRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> WorkflowPreviewResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    classification, steps, warnings = preview_workflow(doc_id, doc, body.preset)
    return WorkflowPreviewResponse(
        doc_id=doc_id,
        preset=body.preset,
        classification=classification,
        steps=steps,
        warnings=warnings,
    )


@router.post("/{doc_id}/workflows/execute", response_model=WorkflowExecuteResponse)
def execute(
    doc_id: str,
    body: WorkflowExecuteRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> WorkflowExecuteResponse:
    record, doc = _load_latest(session, doc_id, actor)
    try:
        return execute_workflow(
            session,
            record,
            doc,
            body.preset,
            actor=actor,
            provenance=get_provenance(session),
            approved_step_ids=set(body.approved_step_ids),
            confirm_destructive=body.confirm_destructive,
            recipients=body.recipients,
            approvers=body.approvers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
