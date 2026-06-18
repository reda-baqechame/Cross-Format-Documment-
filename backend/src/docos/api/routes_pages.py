"""PDF page operations — merge, split, reorder, rotate, delete.

Each op runs on the document's *current* content: the canonical model is written back to
PDF first (so edits and redactions are burned in), then the page operation is applied. The
result is returned as a downloadable PDF, carrying an ``X-DocOS-Validation`` header that
proves the output opens, has the expected page count, and leaks no redacted content. Page ops
require a PDF-origin document.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    MergeRequest,
    PagesRequest,
    ProtectRequest,
    ReorderRequest,
    RotateRequest,
    WatermarkRequest,
)
from docos.api.session import Actor, get_actor
from docos.db.models import Document
from docos.deps import blob_store_dep, db_session, get_provenance
from docos.model.document import CanonicalDocument
from docos.services.docengine import pageops
from docos.services.docengine.writers.pdf_writer import write_back_pdf
from docos.services.provenance import validation
from docos.settings import get_settings
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["pages"])


def _safe(name: str | None, fallback: str) -> str:
    base = (name or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:80]


def _sig_valid(doc: CanonicalDocument) -> bool | None:
    if not doc.signature.signed:
        return None
    from docos.services.provenance import signing

    return signing.verify(doc, secret=get_settings().signing_secret)


async def _current_pdf(record: Document, doc, blob_store: BlobStore) -> bytes:
    """The document's current content as PDF bytes (edits + redactions applied)."""
    if record.source_format != "pdf":
        raise HTTPException(status_code=400, detail="page operations require a PDF document")
    original = await blob_store.get(record.blob_key)
    return write_back_pdf(original, doc)


def _pdf_response(
    data: bytes, name: str, report: validation.ValidationReport | None = None
) -> Response:
    headers = {"Content-Disposition": f'attachment; filename="{name}.pdf"'}
    if report is not None:
        headers["X-DocOS-Validation"] = validation.status(report)
        headers["X-DocOS-Validation-Summary"] = report.summary
    return Response(content=data, media_type="application/pdf", headers=headers)


def _audit(session: Session, doc_id: str, op: str, detail: dict) -> None:
    get_provenance(session).record_event(doc_id, f"pages.{op}", actor="api", detail=detail)
    session.commit()


@router.post("/{doc_id}/pages/rotate")
async def rotate(
    doc_id: str,
    body: RotateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        out = pageops.rotate_pages(pdf, body.pages, body.degrees)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "rotated", {"pages": body.pages, "degrees": body.degrees})
    report = validation.validate_pageop(
        doc, "rotate", out, expected_pages=pageops.page_count(pdf), signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, _safe(record.title, doc_id), report)


@router.post("/{doc_id}/pages/delete")
async def delete(
    doc_id: str,
    body: PagesRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        out = pageops.delete_pages(pdf, body.pages)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "deleted", {"pages": body.pages})
    input_n = pageops.page_count(pdf)
    removed = len({p for p in body.pages if 0 <= p < input_n})
    report = validation.validate_pageop(
        doc, "delete", out, expected_pages=input_n - removed, signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, _safe(record.title, doc_id), report)


@router.post("/{doc_id}/pages/reorder")
async def reorder(
    doc_id: str,
    body: ReorderRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        out = pageops.reorder_pages(pdf, body.order)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "reordered", {"order": body.order})
    report = validation.validate_pageop(
        doc, "reorder", out, expected_pages=len(body.order), signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, _safe(record.title, doc_id), report)


@router.get("/{doc_id}/pages/extract")
async def extract(
    doc_id: str,
    pages: str = Query(..., description="comma-separated 0-based page indices, e.g. 0,2,3"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        indices = [int(p) for p in pages.split(",") if p.strip() != ""]
        out = pageops.extract_pages(pdf, indices)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "extracted", {"pages": indices})
    report = validation.validate_pageop(
        doc, "extract", out, expected_pages=len(indices), signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, f"{_safe(record.title, doc_id)}_extract", report)


@router.post("/{doc_id}/merge")
async def merge_documents(
    doc_id: str,
    body: MergeRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    parts = [await _current_pdf(record, doc, blob_store)]
    for other_id in body.doc_ids:
        other_rec, other_doc = _load_latest(session, other_id, actor)
        parts.append(await _current_pdf(other_rec, other_doc, blob_store))
    try:
        out = pageops.merge(parts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "merged", {"with": body.doc_ids})
    expected = sum(pageops.page_count(p) for p in parts)
    report = validation.validate_pageop(
        doc, "merge", out, expected_pages=expected, signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, f"{_safe(record.title, doc_id)}_merged", report)


@router.post("/{doc_id}/compress")
async def compress(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    out = pageops.compress_pdf(pdf)
    _audit(session, doc_id, "compressed", {"bytes_in": len(pdf), "bytes_out": len(out)})
    report = validation.validate_pageop(
        doc,
        "compress",
        out,
        expected_pages=pageops.page_count(pdf),
        signature_valid=_sig_valid(doc),
    )
    return _pdf_response(out, f"{_safe(record.title, doc_id)}_compressed", report)


@router.post("/{doc_id}/protect")
async def protect(
    doc_id: str,
    body: ProtectRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        out = pageops.encrypt_pdf(
            pdf, body.password, body.owner_password, allow_print=body.allow_print
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "protected", {"allow_print": body.allow_print})
    # Encrypted output: page count is still readable; content is inaccessible by design.
    report = validation.validate_pageop(
        doc, "protect", out, expected_pages=pageops.page_count(pdf), signature_valid=_sig_valid(doc)
    )
    return _pdf_response(out, f"{_safe(record.title, doc_id)}_protected", report)


@router.post("/{doc_id}/watermark")
async def watermark(
    doc_id: str,
    body: WatermarkRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    pdf = await _current_pdf(record, doc, blob_store)
    try:
        out = pageops.watermark_pdf(pdf, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(session, doc_id, "watermarked", {"text": body.text})
    report = validation.validate_pageop(
        doc,
        "watermark",
        out,
        expected_pages=pageops.page_count(pdf),
        signature_valid=_sig_valid(doc),
    )
    return _pdf_response(out, f"{_safe(record.title, doc_id)}_watermarked", report)
