"""Bulk send — one packet to many recipients.

Sends the *same* document to many recipients by stamping out an independent copy per
recipient (new ids + version lineage, via ``services/templates``) and starting a
single-approver sign-off workflow on each copy. Recipients act on their own packet, so
one rejection never blocks the others — the classic "send for signature to N people" flow.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.access import get_owned_document
from docos.api.routes_documents import _load_latest
from docos.api.routes_share import create_recipient_share
from docos.api.session import Actor, get_actor
from docos.db.models import ApprovalStep, BulkSendPacket, Document, DocumentShare
from docos.deps import db_session, get_provenance
from docos.services.auth.share_tokens import recover_share_token
from docos.services.collab import approvals
from docos.services.templates import library
from docos.settings import get_settings

router = APIRouter(prefix="/documents", tags=["bulk-send"])


Recipient = Annotated[str, Field(min_length=1, max_length=200)]


class BulkSendRequest(BaseModel):
    recipients: list[Recipient] = Field(min_length=1, max_length=100)
    message: str | None = Field(default=None, max_length=2_000)


class PacketView(BaseModel):
    recipient: str
    packet_doc_id: str
    state: str  # approval state of this recipient's packet
    portal_url: str | None = None


class BulkSendBatch(BaseModel):
    batch_id: str
    source_doc_id: str
    message: str | None
    packets: list[PacketView]


class BulkSendListResponse(BaseModel):
    source_doc_id: str
    batches: list[BulkSendBatch]


def _packet_state(session: Session, packet_doc_id: str) -> str:
    steps = list(
        session.scalars(select(ApprovalStep).where(ApprovalStep.document_id == packet_doc_id)).all()
    )
    return approvals.overall_state(steps)


def _portal_url(session: Session, packet_doc_id: str, recipient: str) -> str | None:
    share = session.scalar(
        select(DocumentShare)
        .where(
            DocumentShare.document_id == packet_doc_id,
            DocumentShare.recipient_label == recipient,
            DocumentShare.revoked.is_(False),
        )
        .order_by(DocumentShare.created_at.desc())
        .limit(1)
    )
    if share is None:
        return None
    token = recover_share_token(
        share.token,
        share.token_ciphertext,
        secret=get_settings().signing_secret,
        share_id=share.id,
    )
    return f"/portal/{token}"


@router.post("/{doc_id}/bulk-send", response_model=BulkSendBatch)
def bulk_send(
    doc_id: str,
    body: BulkSendRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> BulkSendBatch:
    record, doc = _load_latest(session, doc_id, actor)
    recipients = [r.strip() for r in body.recipients if r.strip()]
    if not recipients:
        raise HTTPException(status_code=422, detail="at least one recipient is required")
    if len(set(recipients)) != len(recipients):
        raise HTTPException(status_code=422, detail="recipients must be unique")

    provenance = get_provenance(session)
    snapshot = library.snapshot(doc)
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    base_title = record.title or doc_id

    packets: list[PacketView] = []
    for recipient in recipients:
        copy = library.instantiate(snapshot, title=f"{base_title} — {recipient}")
        packet_record = Document(
            id=copy.doc_id,
            title=copy.meta.title,
            source_format=copy.meta.source_format,
            source_mime=copy.meta.source_mime,
            blob_key="",
            owner_session_id=actor.session_id,
        )
        session.add(packet_record)
        session.flush()
        version_id = provenance.commit_version(copy)
        packet_record.current_version_id = version_id

        # Each recipient gets a one-step sign-off workflow on their own copy.
        workflow_id = uuid.uuid4().hex
        session.add(
            ApprovalStep(
                document_id=copy.doc_id,
                workflow_id=workflow_id,
                order_index=0,
                approver=recipient,
                ordered=True,
                status=approvals.PENDING,
            )
        )
        session.add(
            BulkSendPacket(
                batch_id=batch_id,
                source_doc_id=doc_id,
                recipient=recipient,
                packet_doc_id=copy.doc_id,
                message=body.message,
            )
        )
        create_recipient_share(
            session,
            doc_id=copy.doc_id,
            actor=actor,
            recipient=recipient,
            permission="sign",
        )
        provenance.record_event(
            copy.doc_id,
            "bulk_send.packet_created",
            actor="api",
            detail={"batch_id": batch_id, "recipient": recipient, "source_doc_id": doc_id},
        )
        packets.append(
            PacketView(
                recipient=recipient,
                packet_doc_id=copy.doc_id,
                state="in_progress",
                portal_url=_portal_url(session, copy.doc_id, recipient),
            )
        )

    provenance.record_event(
        doc_id,
        "bulk_send.created",
        actor="api",
        detail={"batch_id": batch_id, "recipients": recipients},
    )
    session.commit()
    return BulkSendBatch(
        batch_id=batch_id, source_doc_id=doc_id, message=body.message, packets=packets
    )


@router.get("/{doc_id}/bulk-send", response_model=BulkSendListResponse)
def list_bulk_sends(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> BulkSendListResponse:
    get_owned_document(session, doc_id, actor)
    rows = session.scalars(
        select(BulkSendPacket)
        .where(BulkSendPacket.source_doc_id == doc_id)
        .order_by(BulkSendPacket.created_at)
    ).all()

    batches: dict[str, BulkSendBatch] = {}
    for row in rows:
        batch = batches.get(row.batch_id)
        if batch is None:
            batch = BulkSendBatch(
                batch_id=row.batch_id,
                source_doc_id=doc_id,
                message=row.message,
                packets=[],
            )
            batches[row.batch_id] = batch
        batch.packets.append(
            PacketView(
                recipient=row.recipient,
                packet_doc_id=row.packet_doc_id,
                state=_packet_state(session, row.packet_doc_id),
                portal_url=_portal_url(session, row.packet_doc_id, row.recipient),
            )
        )
    return BulkSendListResponse(source_doc_id=doc_id, batches=list(batches.values()))
