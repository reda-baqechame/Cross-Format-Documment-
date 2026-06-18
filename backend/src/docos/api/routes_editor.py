"""Embedded editor sessions.

The current canonical editor stays available, but native DOCX/XLSX/PPTX/PDF editors can
be plugged in through provider config. Until a provider is configured, these routes return
clear warnings instead of pretending local editing has full Office/Acrobat fidelity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    EditorSessionRequest,
    EditorSessionResponse,
    EditorSessionSaveRequest,
    EditorSessionSyncRequest,
)
from docos.api.session import Actor, get_actor
from docos.db.models import EditorSession
from docos.deps import db_session, get_provenance, get_settings
from docos.services.editor import build_editor_session

router = APIRouter(prefix="/documents", tags=["editor"])


def _response(
    doc_id: str,
    source_format: str,
    row: EditorSession,
    warnings: list[str] | None = None,
) -> EditorSessionResponse:
    config = row.config or {}
    return EditorSessionResponse(
        doc_id=doc_id,
        session_id=row.id,
        provider=row.provider,
        status=row.status,
        mode=row.mode,
        source_format=source_format,
        editor_url=str(config.get("editor_url") or ""),
        config=dict(config.get("provider_config") or {}),
        capabilities=list(config.get("capabilities") or []),
        warnings=warnings if warnings is not None else list(config.get("warnings") or []),
        saved_version_id=row.saved_version_id,
    )


def _load_editor_session(
    session: Session, doc_id: str, session_id: str, actor: Actor
) -> tuple[str, EditorSession]:
    record, _doc = _load_latest(session, doc_id, actor)
    row = session.get(EditorSession, session_id)
    if row is None or row.document_id != doc_id:
        raise HTTPException(status_code=404, detail="editor session not found")
    return record.source_format, row


@router.post("/{doc_id}/editor/session", response_model=EditorSessionResponse)
def create_editor_session(
    doc_id: str,
    body: EditorSessionRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> EditorSessionResponse:
    record, doc = _load_latest(session, doc_id, actor)
    provider = build_editor_session(doc, get_settings(), requested_provider=body.provider)
    session_id = f"eds_{uuid.uuid4().hex[:16]}"
    row = EditorSession(
        id=session_id,
        document_id=doc_id,
        provider=provider.provider,
        mode=body.mode or "edit",
        status="created",
        config={
            "editor_url": provider.editor_url,
            "provider_config": provider.config,
            "capabilities": provider.capabilities,
            "warnings": provider.warnings,
        },
    )
    session.add(row)
    get_provenance(session).record_event(
        doc_id,
        "editor.session_created",
        actor=actor.session_id,
        detail={"session_id": session_id, "provider": provider.provider, "mode": row.mode},
    )
    session.commit()
    return _response(doc_id, record.source_format, row, provider.warnings)


@router.get("/{doc_id}/editor/session/{session_id}", response_model=EditorSessionResponse)
def get_editor_session(
    doc_id: str,
    session_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> EditorSessionResponse:
    source_format, row = _load_editor_session(session, doc_id, session_id, actor)
    return _response(doc_id, source_format, row)


@router.post("/{doc_id}/editor/session/{session_id}/save", response_model=EditorSessionResponse)
def save_editor_session(
    doc_id: str,
    session_id: str,
    body: EditorSessionSaveRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> EditorSessionResponse:
    record, row = _load_editor_session(session, doc_id, session_id, actor)
    row.status = "saved"
    row.saved_version_id = _load_latest(session, doc_id, actor)[0].current_version_id
    row.updated_at = datetime.now(UTC)
    get_provenance(session).record_event(
        doc_id,
        "editor.session_saved",
        actor=actor.session_id,
        detail={"session_id": session_id, "provider": row.provider, "note": body.note},
    )
    session.commit()
    return _response(doc_id, record, row)


@router.post("/{doc_id}/editor/session/{session_id}/sync", response_model=EditorSessionResponse)
def sync_editor_session(
    doc_id: str,
    session_id: str,
    body: EditorSessionSyncRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> EditorSessionResponse:
    source_format, row = _load_editor_session(session, doc_id, session_id, actor)
    row.status = "synced"
    row.updated_at = datetime.now(UTC)
    get_provenance(session).record_event(
        doc_id,
        "editor.session_synced",
        actor=actor.session_id,
        detail={"session_id": session_id, "client_revision": body.client_revision},
    )
    session.commit()
    return _response(doc_id, source_format, row)
