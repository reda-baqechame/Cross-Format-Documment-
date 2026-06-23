"""Export & preview — getting documents *out* of the system.

``/export`` serialises the latest canonical model to a downloadable file (TXT today,
plus a universal DOCX writer so any opened document — including PDFs — can download as
Word). ``/preview`` rasterises a PDF page to PNG for the canvas backdrop.

Every produced file is run through the validation engine
(:mod:`docos.services.provenance.validation`): downloads carry an ``X-DocOS-Validation``
header and ``/export/report`` returns the full proof report (output opens, pages preserved,
redactions unrecoverable, seal status) — proof, not just bytes.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document
from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import ValidationReportResponse
from docos.api.session import Actor, get_actor
from docos.deps import blob_store_dep, db_session, get_provenance, get_registry
from docos.model.document import CanonicalDocument
from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.registry import AdapterRegistry
from docos.services.docengine.writers.docx_writer import model_to_docx
from docos.services.docengine.writers.image_writer import model_to_png
from docos.services.docengine.writers.markup import (
    model_to_csv,
    model_to_html,
    model_to_markdown,
    model_to_rtf,
)
from docos.services.docengine.writers.pptx_writer import model_to_pptx
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.docengine.writers.searchable_pdf import model_to_searchable_pdf
from docos.services.docengine.writers.xlsx_writer import model_to_xlsx
from docos.services.provenance import validation
from docos.settings import get_settings
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["export"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_FORMATS = {
    "txt": ("txt", "text/plain", "txt"),
    "docx": ("docx", _DOCX_MIME, "docx"),
}
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# Function-based writers that serialise the canonical model directly (no adapter needed).
# All return bytes. docx/pptx are handled separately because they can embed image bytes.
_DIRECT_WRITERS = {
    "md": (model_to_markdown, "text/markdown", "md"),
    "html": (model_to_html, "text/html", "html"),
    "csv": (model_to_csv, "text/csv", "csv"),
    "rtf": (model_to_rtf, "application/rtf", "rtf"),
    "xlsx": (model_to_xlsx, _XLSX_MIME, "xlsx"),
    "png": (model_to_png, "image/png", "png"),
}


def _safe_filename(name: str | None, fallback: str) -> str:
    base = (name or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:80]


def _signature_valid(doc: CanonicalDocument) -> bool | None:
    """Whether the document's integrity seal still matches its content (None if unsigned)."""
    if not doc.signature.signed:
        return None
    from docos.services.provenance import signing

    return signing.verify(doc, secret=get_settings().signing_secret)


def _validation_headers(report: validation.ValidationReport) -> dict[str, str]:
    return {
        "X-DocOS-Validation": validation.status(report),
        "X-DocOS-Validation-Summary": report.summary,
    }


async def _load_image_bytes(doc: CanonicalDocument, blob_store: BlobStore) -> dict[str, bytes]:
    """Fetch persisted, non-redacted image bytes keyed by ``blob_ref`` for embedding in exports."""
    out: dict[str, bytes] = {}
    for node in doc.nodes.values():
        if node.type != "image" or not node.attrs.get("persisted"):
            continue
        ref = getattr(node, "blob_ref", None)
        if not ref or ref in out or is_redacted(doc, node.id):
            continue
        try:
            out[ref] = await blob_store.get(ref)
        except Exception:  # noqa: BLE001 - a missing blob just falls back to a placeholder
            continue
    return out


async def _render_export(
    doc: CanonicalDocument,
    record,
    fmt: str,
    registry: AdapterRegistry,
    blob_store: BlobStore,
) -> tuple[bytes, str, str]:
    """Produce the export bytes for ``fmt`` → ``(data, mime, ext)``. Shared by download + report."""
    if fmt == "pdf":
        if record.source_format != "pdf":
            raise HTTPException(
                status_code=400, detail="PDF export is only available for PDF documents — use DOCX"
            )
        from docos.services.docengine.writers.pdf_writer import write_back_pdf

        original = await blob_store.get(record.blob_key)
        return write_back_pdf(original, doc), "application/pdf", "pdf"

    # DOCX and PPTX can embed real image bytes — load them once and pass to the writer.
    if fmt == "docx":
        images = await _load_image_bytes(doc, blob_store)
        return model_to_docx(doc, images), _DOCX_MIME, "docx"
    if fmt == "pptx":
        images = await _load_image_bytes(doc, blob_store)
        return model_to_pptx(doc, images), _PPTX_MIME, "pptx"

    if fmt in _DIRECT_WRITERS:
        writer, mime, ext = _DIRECT_WRITERS[fmt]
        return writer(doc), mime, ext

    if fmt in _FORMATS:
        format_id, mime, ext = _FORMATS[fmt]
        try:
            return registry.resolve_by_format(format_id).export(doc, target_mime=mime), mime, ext
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    raise HTTPException(status_code=400, detail=f"unsupported export format: {fmt}")


@router.get("/{doc_id}/export")
async def export_document(
    doc_id: str,
    format: str = Query("docx"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> Response:
    record, doc = _load_latest(session, doc_id, actor)
    data, mime, ext = await _render_export(doc, record, format, registry, blob_store)
    report = validation.validate_export(doc, format, data, signature_valid=_signature_valid(doc))

    get_provenance(session).record_event(
        doc_id, "document.exported", actor=actor.session_id, detail={"format": format}
    )
    session.commit()

    filename = f"{_safe_filename(record.title, doc_id)}.{ext}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        **_validation_headers(report),
    }
    return Response(content=data, media_type=mime, headers=headers)


@router.get("/{doc_id}/export/report", response_model=ValidationReportResponse)
async def export_report(
    doc_id: str,
    format: str = Query("docx"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> ValidationReportResponse:
    """Render the export in-memory and return the validation report (no file download)."""
    record, doc = _load_latest(session, doc_id, actor)
    data, _mime, _ext = await _render_export(doc, record, format, registry, blob_store)
    report = validation.validate_export(doc, format, data, signature_valid=_signature_valid(doc))
    return ValidationReportResponse(doc_id=doc_id, validation=report)


@router.get("/{doc_id}/searchable-pdf")
async def searchable_pdf(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
    registry: AdapterRegistry = Depends(get_registry),
    _rate: None = Depends(enforce_op_rate),
) -> Response:
    """Produce a searchable PDF: scans get an invisible OCR text layer over the page
    image; every other format becomes a clean, born-digital selectable-text PDF."""
    record, doc = _load_latest(session, doc_id, actor)
    page_images: dict[int, bytes] = {}

    if record.source_format == "image" and record.blob_key:
        page_images[0] = await blob_store.get(record.blob_key)
    elif record.source_format == "pdf" and record.blob_key:
        original = await blob_store.get(record.blob_key)
        adapter = registry.resolve_by_format("pdf")
        page_count = sum(1 for n in doc.children_of(doc.root_id) if n.type == "page")
        for i in range(page_count):
            try:
                page_images[i] = adapter.render_preview_bytes(original, page=i)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - fall back to born-digital text for that page
                continue

    data = model_to_searchable_pdf(doc, page_images)
    report = validation.validate_export(
        doc, "searchable-pdf", data, signature_valid=_signature_valid(doc)
    )

    get_provenance(session).record_event(
        doc_id, "document.exported", actor=actor.session_id, detail={"format": "searchable-pdf"}
    )
    session.commit()
    filename = f"{_safe_filename(record.title, doc_id)}_searchable.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        **_validation_headers(report),
    }
    return Response(content=data, media_type="application/pdf", headers=headers)


@router.get("/{doc_id}/preview")
async def preview_page(
    doc_id: str,
    page: int = Query(0, ge=0),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
    registry: AdapterRegistry = Depends(get_registry),
) -> Response:
    record = get_owned_document(session, doc_id, actor)
    if record.source_format not in ("pdf", "image"):
        raise HTTPException(
            status_code=400, detail="preview is only available for PDF and image documents"
        )

    data = await blob_store.get(record.blob_key)
    headers = {"Cache-Control": "private, max-age=300"}

    # Image documents are their own preview — serve the original bytes.
    if record.source_format == "image":
        return Response(content=data, media_type=record.source_mime, headers=headers)

    adapter = registry.resolve_by_format("pdf")
    if not isinstance(adapter, PdfAdapter):  # pragma: no cover - registry wiring guard
        raise HTTPException(status_code=500, detail="pdf adapter unavailable")
    try:
        png = adapter.render_preview_bytes(data, page=page)
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="page out of range") from exc
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/{doc_id}/slide-thumbnail")
def slide_thumbnail(
    doc_id: str,
    node_id: str = Query(..., description="the page/slide node to render"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> Response:
    """A structural PNG thumbnail of a single slide/page, rendered from the canonical model.

    This is a model-rendered *structural* preview (text/tables) — not a PowerPoint-grade raster,
    which would need a rendering engine (provider-gated). It lets the deck editor show real slide
    content for every format (pptx/docx/…), not just PDF.
    """
    _record, doc = _load_latest(session, doc_id, actor)
    node = doc.nodes.get(node_id)
    if node is None or node.type != "page":
        raise HTTPException(status_code=404, detail="slide/page node not found")
    png = model_to_png(doc, root_id=node_id)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=120"},
    )
