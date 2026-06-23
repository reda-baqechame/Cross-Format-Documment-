"""Cloud IDP + handwriting extraction (gated seam).

Returns key/value fields from a document. When a cloud IDP (Textract/external) is configured it is
used and ``used_provider`` is true; otherwise this falls back to the deterministic local extractor
so the endpoint always works. When a handwriting model is configured and the source is an image, its
recognized text is added. Honest: with nothing configured, the result is the local extraction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import IdpExtractResponse, IdpFieldSchema
from docos.api.session import Actor, get_actor
from docos.deps import (
    blob_store_dep,
    db_session,
    get_handwriting_provider,
    get_idp_provider,
)
from docos.services.semantic.extract import extract
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["idp"])


@router.get("/{doc_id}/idp-extract", response_model=IdpExtractResponse)
async def idp_extract(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
    idp=Depends(get_idp_provider),
    handwriting=Depends(get_handwriting_provider),
    _rate: None = Depends(enforce_op_rate),
) -> IdpExtractResponse:
    record, doc = _load_latest(session, doc_id, actor)

    if idp is not None:
        data = await blob_store.get(record.blob_key)
        fields = idp.analyze(data, record.source_mime)
        return IdpExtractResponse(
            doc_id=doc_id,
            provider=idp.name,
            used_provider=True,
            fields=[
                IdpFieldSchema(key=f.key, value=f.value, confidence=f.confidence) for f in fields
            ],
            detail=f"Extracted by the {idp.name} cloud IDP.",
        )

    # Local fallback: the deterministic extractor over the canonical model (redaction-aware).
    local = extract(doc)
    fields = [IdpFieldSchema(key=f.key, value=f.value, confidence=1.0) for f in local.fields]
    detail = "Local extraction (no cloud IDP configured)."

    # Optional handwriting augmentation for scanned/image sources.
    if handwriting is not None and record.source_format == "image":
        data = await blob_store.get(record.blob_key)
        text = handwriting.recognize(data, record.source_mime)
        if text.strip():
            fields.append(IdpFieldSchema(key="handwriting", value=text.strip(), confidence=0.0))
            detail += " Handwriting recognized by the configured model."

    return IdpExtractResponse(
        doc_id=doc_id, provider="local", used_provider=False, fields=fields, detail=detail
    )
