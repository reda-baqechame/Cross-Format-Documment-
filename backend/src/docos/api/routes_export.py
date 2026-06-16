"""Export & preview — getting documents *out* of the system.

``/export`` serialises the latest canonical model to a downloadable file (TXT today,
plus a universal DOCX writer so any opened document — including PDFs — can download as
Word). ``/preview`` rasterises a PDF page to PNG for the canvas backdrop.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.db.models import Document
from docos.deps import blob_store_dep, db_session, get_provenance, get_registry
from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.registry import AdapterRegistry
from docos.services.docengine.writers.markup import (
    model_to_csv,
    model_to_html,
    model_to_markdown,
)
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["export"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_FORMATS = {
    "txt": ("txt", "text/plain", "txt"),
    "docx": ("docx", _DOCX_MIME, "docx"),
}
# Function-based writers that serialise the canonical model directly (no adapter needed).
_DIRECT_WRITERS = {
    "md": (model_to_markdown, "text/markdown", "md"),
    "html": (model_to_html, "text/html", "html"),
    "csv": (model_to_csv, "text/csv", "csv"),
}


def _safe_filename(name: str | None, fallback: str) -> str:
    base = (name or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:80]


@router.get("/{doc_id}/export")
async def export_document(
    doc_id: str,
    format: str = Query("docx"),
    session: Session = Depends(db_session),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    if format == "pdf":
        return await _export_pdf(doc_id, session, blob_store)

    if format in _DIRECT_WRITERS:
        record, doc = _load_latest(session, doc_id)
        writer, mime, ext = _DIRECT_WRITERS[format]
        data = writer(doc)
    elif format in _FORMATS:
        record, doc = _load_latest(session, doc_id)
        format_id, mime, ext = _FORMATS[format]
        try:
            data = registry.resolve_by_format(format_id).export(doc, target_mime=mime)
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail=f"unsupported export format: {format}")

    provenance = get_provenance(session)
    provenance.record_event(doc_id, "document.exported", actor="api", detail={"format": format})
    session.commit()

    filename = f"{_safe_filename(record.title, doc_id)}.{ext}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _export_pdf(doc_id: str, session: Session, blob_store: BlobStore) -> Response:
    """PDF write-back: re-emit the original PDF with edits applied and redactions burned in."""
    record, doc = _load_latest(session, doc_id)
    if record.source_format != "pdf":
        raise HTTPException(
            status_code=400, detail="PDF export is only available for PDF documents — use DOCX"
        )
    from docos.services.docengine.writers.pdf_writer import write_back_pdf

    original = await blob_store.get(record.blob_key)
    data = write_back_pdf(original, doc)

    get_provenance(session).record_event(
        doc_id, "document.exported", actor="api", detail={"format": "pdf"}
    )
    session.commit()
    filename = f"{_safe_filename(record.title, doc_id)}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/preview")
async def preview_page(
    doc_id: str,
    page: int = Query(0, ge=0),
    session: Session = Depends(db_session),
    blob_store: BlobStore = Depends(blob_store_dep),
    registry: AdapterRegistry = Depends(get_registry),
) -> Response:
    record = session.get(Document, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="document not found")
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
