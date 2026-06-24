"""E-signature requests (gated provider seam).

With the default ``seal`` provider, a request applies the integrity seal (tamper-evident, **not**
legally binding) and is recorded honestly. With an external regulated provider configured, the
document is sent for signature and tracked by ``external_id``; a verified webhook updates status.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    SignatureRequestCreate,
    SignatureRequestResponse,
)
from docos.api.session import Actor, get_actor
from docos.db.models import Document, SignatureRequest
from docos.deps import (
    blob_store_dep,
    db_session,
    get_provenance,
    get_registry,
    get_signature_provider,
)
from docos.services.docengine.registry import AdapterRegistry
from docos.services.esign import SignatureProvider, Signer, verify_webhook
from docos.services.provenance import signing
from docos.settings import get_settings
from docos.storage.blob import BlobStore

router = APIRouter(tags=["esign"])


def _to_response(
    doc_id: str,
    row: SignatureRequest,
    *,
    signing_url: str | None,
    detail: str,
    legally_binding: bool,
) -> SignatureRequestResponse:
    return SignatureRequestResponse(
        id=row.id,
        doc_id=doc_id,
        provider=row.provider,
        status=row.status,
        signing_url=signing_url,
        detail=detail,
        legally_binding=legally_binding,
    )


async def _native_pdf(
    doc, record: Document, registry: AdapterRegistry, blob_store: BlobStore
) -> bytes:
    """Render the document to PDF bytes for an external signature provider."""
    from docos.services.docengine.writers.pdf_writer import write_back_pdf
    from docos.services.docengine.writers.searchable_pdf import model_to_searchable_pdf

    if record.source_format == "pdf":
        original = await blob_store.get(record.blob_key)
        return write_back_pdf(original, doc)
    return model_to_searchable_pdf(doc)


@router.post("/documents/{doc_id}/signature-request", response_model=SignatureRequestResponse)
async def create_signature_request(
    doc_id: str,
    body: SignatureRequestCreate,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    provider: SignatureProvider = Depends(get_signature_provider),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> SignatureRequestResponse:
    record, doc = _load_latest(session, doc_id, actor)
    signers = [Signer(name=s.name, email=s.email) for s in body.signers]
    subject = body.subject or (doc.meta.title or f"Document {doc_id[:8]}")

    if provider.name == "seal":
        # Honest default: apply the tamper-evident integrity seal and record it.
        secret = get_settings().signing_secret
        signed = signing.sign(doc, signer=(signers[0].name if signers else "Signer"), secret=secret)
        prov = get_provenance(session)
        record.current_version_id = prov.commit_version(signed)
        result = provider.create_request(
            document=b"", filename="", signers=signers, subject=subject
        )
    else:
        document = await _native_pdf(doc, record, registry, blob_store)
        result = provider.create_request(
            document=document, filename=f"{doc_id}.pdf", signers=signers, subject=subject
        )
        if result.status == "error":
            raise HTTPException(
                status_code=502, detail=f"signature provider error: {result.detail}"
            )

    row = SignatureRequest(
        id=f"sig_{uuid.uuid4().hex[:16]}",
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        document_id=doc_id,
        provider=result.provider,
        external_id=result.external_id,
        status=result.status,
        subject=subject,
        signers=[s.model_dump() for s in signers],
    )
    session.add(row)
    get_provenance(session).record_event(
        doc_id,
        "esign.requested",
        actor="api",
        detail={"provider": result.provider, "status": result.status},
    )
    session.commit()
    return _to_response(
        doc_id,
        row,
        signing_url=result.signing_url,
        detail=result.detail,
        legally_binding=result.legally_binding,
    )


@router.get("/signature-requests/{request_id}", response_model=SignatureRequestResponse)
def get_signature_request(
    request_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    provider: SignatureProvider = Depends(get_signature_provider),
) -> SignatureRequestResponse:
    row = session.get(SignatureRequest, request_id)
    if row is None or (
        row.owner_session_id != actor.session_id
        and (actor.user_id is None or row.owner_user_id != actor.user_id)
    ):
        raise HTTPException(status_code=404, detail="signature request not found")
    signing_url, detail, binding = None, "", row.provider == "external"
    # Refresh from the external provider when applicable.
    if row.provider == "external" and row.external_id and provider.name == "external":
        result = provider.status(row.external_id)
        if result.status != "error":
            row.status = result.status
            signing_url = result.signing_url
            session.commit()
    return _to_response(
        row.document_id, row, signing_url=signing_url, detail=detail, legally_binding=binding
    )


@router.post("/esign/webhook")
async def esign_webhook(request: Request, session: Session = Depends(db_session)) -> dict:
    """Provider → us status callback, authenticated by an HMAC signature header."""
    settings = get_settings()
    if not settings.esign_configured:
        raise HTTPException(status_code=501, detail="external e-signature provider not configured")
    payload = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not verify_webhook(payload, signature, settings.signature_provider_key or ""):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    body = await request.json()
    external_id = str(body.get("id", ""))
    new_status = str(body.get("status", ""))
    if external_id and new_status:
        row = (
            session.execute(
                select(SignatureRequest).where(SignatureRequest.external_id == external_id)
            )
            .scalars()
            .first()
        )
        if row is not None:
            row.status = new_status
            row.updated_at = datetime.now(UTC)
            session.commit()
    return {"ok": True}
