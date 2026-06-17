"""Bulk send — one packet to many recipients.

Sends the *same* document to many recipients by stamping out an independent copy per
recipient (new ids + version lineage, via ``services/templates``) and starting a
single-approver sign-off workflow on each copy. Recipients act on their own packet, so
one rejection never blocks the others — the classic "send for signature to N people" flow.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.db.models import ApprovalStep, BulkSendPacket, Document
from docos.deps import db_session, get_provenance
from docos.services.collab import approvals
from docos.services.templates import library

router = APIRouter(prefix="/documents", tags=["bulk-send"])


class BulkSendRequest(BaseModel):
    recipients: list[str]
    message: str | None = None


class PacketView(BaseModel):
    recipient: str
    packet_doc_id: str
    state: str  # approval state of this recipient's packet


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
        session.scalars(
            select(ApprovalStep).where(ApprovalStep.document_id == packet_doc_id)
        ).all()
    )
    return approvals.overall_state(steps)


@router.post("/{doc_id}/bulk-send", response_model=BulkSendBatch)
def bulk_send(
    doc_id: str, body: BulkSendRequest, session: Session = Depends(db_session)
) -> BulkSendBatch:
    record, doc = _load_latest(session, doc_id)
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
        provenance.record_event(
            copy.doc_id,
            "bulk_send.packet_created",
            actor="api",
            detail={"batch_id": batch_id, "recipient": recipient, "source_doc_id": doc_id},
        )
        packets.append(
            PacketView(recipient=recipient, packet_doc_id=copy.doc_id, state="in_progress")
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
def list_bulk_sends(doc_id: str, session: Session = Depends(db_session)) -> BulkSendListResponse:
    if session.get(Document, doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
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
            )
        )
    return BulkSendListResponse(source_doc_id=doc_id, batches=list(batches.values()))
