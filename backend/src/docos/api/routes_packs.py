"""Business-pack endpoints. First: import/export shipment-packet validation.

Additive + read-only: loads the caller's own documents, runs the deterministic packet checker, and
returns a consistency report + customs checklist. No mutation, no LLM, no network.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.deps import db_session
from docos.services.packs import (
    APReport,
    ContractReport,
    PacketReport,
    check_ap,
    check_contracts,
    check_packet,
)

router = APIRouter(prefix="/packs", tags=["packs"])


class ImportExportCheckRequest(BaseModel):
    doc_ids: list[str]


class APCheckRequest(BaseModel):
    doc_ids: list[str]


class ContractCheckRequest(BaseModel):
    doc_ids: list[str]


@router.post("/import-export/check", response_model=PacketReport)
def import_export_check(
    body: ImportExportCheckRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> PacketReport:
    """Validate an import/export shipment packet across the given documents (owner-scoped)."""
    if not body.doc_ids:
        raise HTTPException(status_code=422, detail="at least one doc_id is required")
    corpus = load_corpus(
        session,
        body.doc_ids,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="no matching documents found")
    return check_packet([(c.doc_id, c.title, c.doc) for c in corpus])


@router.post("/finance/ap-check", response_model=APReport)
def finance_ap_check(
    body: APCheckRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> APReport:
    """Match invoices to POs + flag duplicate invoices across the given documents (owner-scoped)."""
    if not body.doc_ids:
        raise HTTPException(status_code=422, detail="at least one doc_id is required")
    corpus = load_corpus(
        session,
        body.doc_ids,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="no matching documents found")
    return check_ap([(c.doc_id, c.title, c.doc) for c in corpus])


@router.post("/contracts/check", response_model=ContractReport)
def contracts_check(
    body: ContractCheckRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> ContractReport:
    """Extract key contract terms + flag common review risks across the docs (owner-scoped)."""
    if not body.doc_ids:
        raise HTTPException(status_code=422, detail="at least one doc_id is required")
    corpus = load_corpus(
        session,
        body.doc_ids,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="no matching documents found")
    return check_contracts([(c.doc_id, c.title, c.doc) for c in corpus])
