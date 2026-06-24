"""Document upload + canonical-model retrieval — the core vertical slice.

POST /documents runs the full pipeline: ingestion validate → scan → stage →
adapter.parse → persist Document + commit version + audit. The model is then
retrievable and the source of truth for the frontend canvas.

Every document is owned by the caller's anonymous session (see :mod:`docos.api.session`),
and every route here loads it through :func:`docos.api.access.get_owned_document`, so one
session can never read, list, or delete another's documents.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document, owner_clause
from docos.api.ratelimit import enforce_upload_rate
from docos.api.schemas import (
    AssetUploadResponse,
    DocumentListResponse,
    DocumentModelResponse,
    DocumentSummary,
    HistoryResponse,
    PurgeResponse,
    UploadResponse,
)
from docos.api.session import Actor, get_actor
from docos.db.models import BlobTombstone, Document, DocumentVersion, JobRecord, Label
from docos.deps import (
    blob_store_dep,
    db_session,
    get_ingestion_gateway,
    get_provenance,
    get_registry,
)
from docos.model.document import CanonicalDocument
from docos.model.serialize import from_dict
from docos.services.docengine.registry import AdapterRegistry
from docos.services.ingestion.allowlist import sniff_mime
from docos.services.ingestion.interface import IngestionGateway
from docos.storage.blob import BlobStore

logger = logging.getLogger("docos.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

_ASSET_IMAGE_MIMES = {"image/png", "image/jpeg", "image/tiff"}


def _load_latest(session: Session, doc_id: str, actor: Actor) -> tuple[Document, CanonicalDocument]:
    """Load a document's latest model, enforcing ownership (404 on miss/cross-owner)."""
    record = get_owned_document(session, doc_id, actor)
    if record.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    version = session.get(DocumentVersion, record.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="version not found")
    return record, from_dict(version.model)


async def _persist_pending_assets(doc: CanonicalDocument, blob_store: BlobStore) -> None:
    """Write image bytes extracted during ``parse`` to blob storage and mark their nodes persisted.

    Adapters can't ``await`` inside the sync ``parse``, so they stash extracted image bytes on the
    document (``_pending_assets``); we drain them here. Best-effort: a storage failure leaves the
    image as an unpersisted placeholder rather than failing the whole upload.
    """
    pending = getattr(doc, "_pending_assets", {})
    if not pending:
        return
    stored: set[str] = set()
    for ref, data in pending.items():
        try:
            await blob_store.put(ref, data)
            stored.add(ref)
        except Exception:  # noqa: BLE001 - image persistence is best-effort
            logger.warning("failed to persist image asset %s", ref)
    for node in doc.nodes.values():
        if node.type == "image" and node.blob_ref in stored:
            node.attrs["persisted"] = True
    pending.clear()


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, aborting as soon as it exceeds ``max_bytes``.

    Bounds memory to the limit regardless of a missing or dishonest Content-Length.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"the file is too large (max {max_mb} MB)")
        chunks.append(chunk)
    return b"".join(chunks)


async def ingest_bytes(
    session: Session,
    *,
    filename: str,
    data: bytes,
    actor: Actor,
    gateway: IngestionGateway,
    registry: AdapterRegistry,
    blob_store: BlobStore,
) -> tuple[Document, str, str]:
    """Validate → scan → parse → stage → version a byte payload into a new document.

    Shared by the upload route and the cloud-integration import route so a file pulled from Drive/
    Dropbox/… goes through the exact same validation, malware scan, and provenance pipeline as an
    upload. Returns ``(record, version_id, detected_format)``.
    """
    provenance = get_provenance(session)

    result = await gateway.validate(filename or "upload", data)
    if not result.ok:
        provenance.record_event(
            None, "upload.rejected", actor=actor.session_id, detail={"reason": result.reason}
        )
        session.commit()
        raise HTTPException(status_code=415, detail=result.reason)

    scan = await gateway.scan(data)
    if not scan.clean:
        provenance.record_event(
            None, "upload.infected", actor=actor.session_id, detail={"sig": scan.signature}
        )
        session.commit()
        raise HTTPException(status_code=422, detail="file failed malware scan")

    try:
        adapter = registry.resolve(result.mime)
        doc = adapter.parse(data)
    except (LookupError, NotImplementedError) as exc:
        session.add(
            JobRecord(
                id=uuid.uuid4().hex,
                kind="ingest",
                document_id=None,
                status="failed",
                error=str(exc),
                finished=True,
            )
        )
        session.commit()
        if isinstance(exc, LookupError):
            raise HTTPException(status_code=415, detail=f"no adapter for {result.mime}") from exc
        raise HTTPException(
            status_code=501,
            detail=f"format '{result.detected_format}' not yet supported (stubbed adapter)",
        ) from exc
    except Exception as exc:  # noqa: BLE001 - hostile files may trigger parser-specific errors
        logger.warning("document parse failed for %s: %s", filename, exc)
        session.add(
            JobRecord(
                id=uuid.uuid4().hex,
                kind="ingest",
                document_id=None,
                status="failed",
                error="parse failed",
                finished=True,
            )
        )
        session.commit()
        raise HTTPException(status_code=422, detail="file could not be parsed safely") from exc

    blob_key = await gateway.stage(data, mime=result.mime)
    # Persist any images the adapter extracted so exporters can embed real bytes (not placeholders).
    await _persist_pending_assets(doc, blob_store)

    record = Document(
        id=doc.doc_id,
        title=doc.meta.title,
        source_format=doc.meta.source_format,
        source_mime=doc.meta.source_mime,
        blob_key=blob_key,
        owner_session_id=actor.session_id,
    )
    session.add(record)
    session.flush()

    version_id = provenance.commit_version(doc)
    record.current_version_id = version_id
    provenance.record_event(
        doc.doc_id,
        "document.ingested",
        actor=actor.session_id,
        detail={"format": doc.meta.source_format},
    )
    session.add(
        JobRecord(
            id=uuid.uuid4().hex,
            kind="ingest",
            document_id=doc.doc_id,
            status="succeeded",
            finished=True,
        )
    )
    session.commit()
    return record, version_id, result.detected_format


@router.post("", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(db_session),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_upload_rate),
) -> UploadResponse:
    # Reject oversized uploads before buffering anything when the size is declared.
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > gateway.max_bytes:
        max_mb = gateway.max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"the file is too large (max {max_mb} MB)")

    data = await _read_capped(file, gateway.max_bytes)
    record, version_id, detected_format = await ingest_bytes(
        session,
        filename=file.filename or "upload",
        data=data,
        actor=actor,
        gateway=gateway,
        registry=registry,
        blob_store=blob_store,
    )
    return UploadResponse(doc_id=record.id, version_id=version_id, detected_format=detected_format)


@router.post("/{doc_id}/assets", response_model=AssetUploadResponse)
async def upload_asset(
    doc_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(db_session),
    gateway: IngestionGateway = Depends(get_ingestion_gateway),
    blob_store: BlobStore = Depends(blob_store_dep),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_upload_rate),
) -> AssetUploadResponse:
    """Attach an image asset to a document for insert/replace-image patch ops."""
    get_owned_document(session, doc_id, actor)
    data = await _read_capped(file, gateway.max_bytes)
    mime = sniff_mime(file.filename or "asset", data)
    if mime not in _ASSET_IMAGE_MIMES:
        raise HTTPException(status_code=415, detail="document assets must be PNG, JPEG, or TIFF")
    scan = await gateway.scan(data)
    if not scan.clean:
        get_provenance(session).record_event(
            doc_id, "asset.infected", actor=actor.session_id, detail={"sig": scan.signature}
        )
        session.commit()
        raise HTTPException(status_code=422, detail="asset failed malware scan")
    key = f"assets/{doc_id}/{uuid.uuid4().hex}"
    await blob_store.put(key, data)
    get_provenance(session).record_event(
        doc_id,
        "asset.uploaded",
        actor=actor.session_id,
        detail={"blob_ref": key, "mime": mime, "filename": file.filename},
    )
    session.commit()
    return AssetUploadResponse(doc_id=doc_id, blob_ref=key, mime=mime, filename=file.filename)


@router.get("/{doc_id}/model", response_model=DocumentModelResponse)
def get_model(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> DocumentModelResponse:
    record, doc = _load_latest(session, doc_id, actor)
    return DocumentModelResponse(document=doc, version_id=record.current_version_id)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    tag: str | None = None,
) -> DocumentListResponse:
    records = session.scalars(
        select(Document)
        .where(owner_clause(Document.owner_session_id, Document.owner_user_id, actor))
        .order_by(Document.created_at.desc())
    ).all()
    owned_ids = {r.id for r in records}
    tags_by_doc: dict[str, list[str]] = {}
    for label in session.scalars(select(Label)).all():
        if label.document_id in owned_ids:
            tags_by_doc.setdefault(label.document_id, []).append(label.label)

    summaries = [
        DocumentSummary(
            doc_id=r.id,
            title=r.title,
            source_format=r.source_format,
            current_version_id=r.current_version_id,
            created_at=r.created_at,
            tags=sorted(tags_by_doc.get(r.id, [])),
        )
        for r in records
    ]
    if tag:
        summaries = [s for s in summaries if tag in s.tags]
    return DocumentListResponse(documents=summaries)


@router.get("/{doc_id}/history", response_model=HistoryResponse)
def get_history(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> HistoryResponse:
    get_owned_document(session, doc_id, actor)
    provenance = get_provenance(session)
    return HistoryResponse(doc_id=doc_id, versions=provenance.history(doc_id))


@router.post("/{doc_id}/undo", response_model=DocumentModelResponse)
def undo(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> DocumentModelResponse:
    """Roll the document back to its parent version (version-DAG undo)."""
    record = get_owned_document(session, doc_id, actor)
    if record.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    current = session.get(DocumentVersion, record.current_version_id)
    if current is None or current.parent_id is None:
        raise HTTPException(status_code=409, detail="nothing to undo")

    record.current_version_id = current.parent_id
    get_provenance(session).record_event(
        doc_id, "version.reverted", actor=actor.session_id, detail={"to": current.parent_id}
    )
    session.commit()
    return DocumentModelResponse(
        document=from_dict(session.get(DocumentVersion, current.parent_id).model),
        version_id=current.parent_id,
    )


@router.post("/{doc_id}/redo", response_model=DocumentModelResponse)
def redo(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> DocumentModelResponse:
    """Re-apply the most recently undone edit (version-DAG redo — mirror of undo)."""
    record = get_owned_document(session, doc_id, actor)
    if record.current_version_id is None:
        raise HTTPException(status_code=404, detail="document not found")
    # The newest version whose parent is the current one is the edit we last undid.
    child = (
        session.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == doc_id,
                DocumentVersion.parent_id == record.current_version_id,
            )
            .order_by(DocumentVersion.created_at.desc())
        )
        .scalars()
        .first()
    )
    if child is None:
        raise HTTPException(status_code=409, detail="nothing to redo")

    record.current_version_id = child.id
    get_provenance(session).record_event(
        doc_id, "version.reapplied", actor=actor.session_id, detail={"to": child.id}
    )
    session.commit()
    return DocumentModelResponse(document=from_dict(child.model), version_id=child.id)


@router.delete("", response_model=PurgeResponse)
async def purge_my_documents(
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> PurgeResponse:
    """Delete every document owned by the caller's session (Private Mode "delete all now")."""
    records = session.scalars(
        select(Document).where(Document.owner_session_id == actor.session_id)
    ).all()
    blob_keys = [r.blob_key for r in records if r.blob_key]
    deleted = len(records)
    for record in records:
        session.delete(record)  # versions cascade-delete
    get_provenance(session).record_event(
        None, "documents.purged", actor=actor.session_id, detail={"count": deleted}
    )
    session.commit()

    from docos.deps import get_blob_store

    blob_store = get_blob_store()
    for blob_key in blob_keys:
        try:
            await blob_store.delete(blob_key)
        except Exception as exc:  # noqa: BLE001 - record for retry, never swallow
            logger.warning("blob delete failed for %s: %s", blob_key, exc)
            session.add(
                BlobTombstone(blob_key=blob_key, reason="delete_failed", last_error=str(exc))
            )
    session.commit()
    return PurgeResponse(deleted=deleted)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> None:
    record = get_owned_document(session, doc_id, actor)
    blob_key = record.blob_key
    session.delete(record)  # versions cascade-delete
    get_provenance(session).record_event(
        doc_id, "document.deleted", actor=actor.session_id, detail={}
    )
    session.commit()

    if not blob_key:
        return
    from docos.deps import get_blob_store

    try:
        await get_blob_store().delete(blob_key)
    except Exception as exc:  # noqa: BLE001 - surface, don't swallow: record for retry
        logger.warning("blob delete failed for %s: %s", blob_key, exc)
        session.add(BlobTombstone(blob_key=blob_key, reason="delete_failed", last_error=str(exc)))
        get_provenance(session).record_event(
            doc_id,
            "document.blob_delete_failed",
            actor=actor.session_id,
            detail={"blob_key": blob_key, "error": str(exc)},
        )
        session.commit()
