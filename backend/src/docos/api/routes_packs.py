"""Business-pack endpoints. First: import/export shipment-packet validation.

Additive + read-only: loads the caller's own documents, runs the deterministic packet checker, and
returns a consistency report + customs checklist. No mutation, no LLM, no network.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.deps import db_session
from docos.model.document import CanonicalDocument
from docos.services import synthesis
from docos.services.docengine.writers.docx_writer import model_to_docx
from docos.services.docengine.writers.markup import model_to_html, model_to_markdown
from docos.services.docengine.writers.searchable_pdf import model_to_searchable_pdf
from docos.services.docengine.writers.xlsx_writer import model_to_xlsx
from docos.services.packs import (
    APReport,
    ContractReport,
    HRReport,
    InsuranceReport,
    PacketReport,
    PackInfo,
    check_ap,
    check_contracts,
    check_insurance,
    check_onboarding,
    check_packet,
    list_packs,
)

router = APIRouter(prefix="/packs", tags=["packs"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# pack name → (check fn over (doc_id, title, doc) tuples, report-builder over its DTO)
_PACK_REPORTS = {
    "import-export": (check_packet, synthesis.packet_exception_report),
    "finance": (check_ap, synthesis.ap_reconciliation_report),
    "contracts": (check_contracts, synthesis.contract_risk_report),
    "hr": (check_onboarding, synthesis.hr_onboarding_report),
    "insurance": (check_insurance, synthesis.insurance_review_report),
}

# fmt → (writer over a CanonicalDocument, mime, extension)
_REPORT_WRITERS = {
    "pdf": (model_to_searchable_pdf, "application/pdf", "pdf"),
    "xlsx": (model_to_xlsx, _XLSX_MIME, "xlsx"),
    "docx": (lambda d: model_to_docx(d), _DOCX_MIME, "docx"),
    "html": (model_to_html, "text/html", "html"),
    "md": (model_to_markdown, "text/markdown", "md"),
}


def _render_report(doc: CanonicalDocument, fmt: str) -> tuple[bytes, str, str]:
    writer, mime, ext = _REPORT_WRITERS[fmt]
    return writer(doc), mime, ext


@router.get("", response_model=list[PackInfo])
def list_business_packs() -> list[PackInfo]:
    """List the installed business packs and their endpoints (static metadata, no auth)."""
    return list_packs()


class ImportExportCheckRequest(BaseModel):
    doc_ids: list[str]


class APCheckRequest(BaseModel):
    doc_ids: list[str]


class ContractCheckRequest(BaseModel):
    doc_ids: list[str]


class OnboardingCheckRequest(BaseModel):
    doc_ids: list[str]


class InsuranceCheckRequest(BaseModel):
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


class ReportRequest(BaseModel):
    doc_ids: list[str]


@router.post("/{pack}/report")
def generate_pack_report(
    pack: str,
    body: ReportRequest,
    fmt: str = Query("pdf", alias="format"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> Response:
    """Run a pack and return its findings as a generated, downloadable document.

    This is the deliverable layer: a pack's structured findings become a real exception report /
    reconciliation / review document (PDF/XLSX/DOCX/HTML/MD). Read-only and owner-scoped — it never
    mutates the source documents.
    """
    if pack not in _PACK_REPORTS:
        raise HTTPException(status_code=404, detail=f"unknown pack '{pack}'")
    if fmt not in _REPORT_WRITERS:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported format '{fmt}' — use one of {sorted(_REPORT_WRITERS)}",
        )
    if not body.doc_ids:
        raise HTTPException(status_code=422, detail="at least one doc_id is required")

    corpus = load_corpus(
        session, body.doc_ids, owner_session_id=actor.session_id, owner_user_id=actor.user_id
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="no matching documents found")

    check_fn, report_fn = _PACK_REPORTS[pack]
    report = report_fn(check_fn([(c.doc_id, c.title, c.doc) for c in corpus]))
    doc = synthesis.build_document(report)
    data, mime, ext = _render_report(doc, fmt)
    filename = f"{pack.replace('-', '_')}_report.{ext}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/hr/onboarding-check", response_model=HRReport)
def hr_onboarding_check(
    body: OnboardingCheckRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> HRReport:
    """Extract offer terms + verify onboarding-packet completeness across docs (owner-scoped)."""
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
    return check_onboarding([(c.doc_id, c.title, c.doc) for c in corpus])


@router.post("/insurance/check", response_model=InsuranceReport)
def insurance_check(
    body: InsuranceCheckRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> InsuranceReport:
    """Review insurance policies/claims: expiry, coverage, claim-within-period (owner-scoped)."""
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
    return check_insurance([(c.doc_id, c.title, c.doc) for c in corpus])
