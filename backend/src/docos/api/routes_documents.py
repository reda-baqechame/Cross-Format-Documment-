"""Document upload + canonical-model retrieval — the core vertical slice.

POST /documents runs the full pipeline: ingestion validate → scan → stage →
adapter.parse → persist Document + commit version + audit. The model is then
retrievable and the source of truth for the frontend canvas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.schemas import (
    DocumentListResponse,
    DocumentModelResponse,
    DocumentSummary,
    HistoryResponse,
    UploadResponse,
)
from docos.db.models import Document, DocumentVersion
from docos.deps import db_session, get_ingestion_gateway, get_provenance, get_registry
from docos.model.document import CanonicalDocument
from docos.model.serialize import from_dict
from docos.services.docengine.registry import AdapterRegistry
from docos.services.ingestion.interface import IngestionGateway

router = APIRouter(prefix="/documents", tags=["documents"])


def _load_latest(session: Session, doc_id: str) -> tuple[Document, CanonicalDocument]:
    record = session.get(Document, doc_id)
    if record is None or record.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    from docos.db.models import DocumentVersion

    version = session.get(DocumentVersion, record.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="version not found")
    return record, from_dict(version.model)


@router.post("", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(db_session),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
    registry: AdapterRegistry = Depends(get_registry),
) -> UploadResponse:
    data = await file.read()
    provenance = get_provenance(session)

    result = await gateway.validate(file.filename or "upload", data)
    if not result.ok:
        provenance.record_event(
            None, "upload.rejected", actor="api", detail={"reason": result.reason}
        )
        session.commit()
        raise HTTPException(status_code=415, detail=result.reason)

    scan = await gateway.scan(data)
    if not scan.clean:
        provenance.record_event(
            None, "upload.infected", actor="api", detail={"sig": scan.signature}
        )
        session.commit()
        raise HTTPException(status_code=422, detail="file failed malware scan")

    blob_key = await gateway.stage(data, mime=result.mime)

    try:
        adapter = registry.resolve(result.mime)
        doc = adapter.parse(data)
    except LookupError as exc:
        raise HTTPException(status_code=415, detail=f"no adapter for {result.mime}") from exc
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail=f"format '{result.detected_format}' not yet supported (stubbed adapter)",
        ) from exc

    record = Document(
        id=doc.doc_id,
        title=doc.meta.title,
        source_format=doc.meta.source_format,
        source_mime=doc.meta.source_mime,
        blob_key=blob_key,
    )
    session.add(record)
    session.flush()

    version_id = provenance.commit_version(doc)
    record.current_version_id = version_id
    provenance.record_event(
        doc.doc_id, "document.ingested", actor="api", detail={"format": doc.meta.source_format}
    )
    session.commit()

    return UploadResponse(
        doc_id=doc.doc_id, version_id=version_id, detected_format=result.detected_format
    )


@router.get("/{doc_id}/model", response_model=DocumentModelResponse)
def get_model(doc_id: str, session: Session = Depends(db_session)) -> DocumentModelResponse:
    record, doc = _load_latest(session, doc_id)
    return DocumentModelResponse(document=doc, version_id=record.current_version_id)


@router.get("", response_model=DocumentListResponse)
def list_documents(session: Session = Depends(db_session)) -> DocumentListResponse:
    records = session.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return DocumentListResponse(
        documents=[
            DocumentSummary(
                doc_id=r.id,
                title=r.title,
                source_format=r.source_format,
                current_version_id=r.current_version_id,
                created_at=r.created_at,
            )
            for r in records
        ]
    )


@router.get("/{doc_id}/history", response_model=HistoryResponse)
def get_history(doc_id: str, session: Session = Depends(db_session)) -> HistoryResponse:
    provenance = get_provenance(session)
    return HistoryResponse(doc_id=doc_id, versions=provenance.history(doc_id))


@router.post("/{doc_id}/undo", response_model=DocumentModelResponse)
def undo(doc_id: str, session: Session = Depends(db_session)) -> DocumentModelResponse:
    """Roll the document back to its parent version (version-DAG undo)."""
    record = session.get(Document, doc_id)
    if record is None or record.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    current = session.get(DocumentVersion, record.current_version_id)
    if current is None or current.parent_id is None:
        raise HTTPException(status_code=409, detail="nothing to undo")

    record.current_version_id = current.parent_id
    get_provenance(session).record_event(
        doc_id, "version.reverted", actor="api", detail={"to": current.parent_id}
    )
    session.commit()
    return DocumentModelResponse(
        document=from_dict(session.get(DocumentVersion, current.parent_id).model),
        version_id=current.parent_id,
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, session: Session = Depends(db_session)) -> None:
    record = session.get(Document, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="document not found")
    blob_key = record.blob_key
    session.delete(record)  # versions cascade-delete
    get_provenance(session).record_event(doc_id, "document.deleted", actor="api", detail={})
    session.commit()
    try:
        from docos.deps import get_blob_store

        await get_blob_store().delete(blob_key)
    except Exception:  # noqa: BLE001 - blob cleanup is best-effort
        pass
