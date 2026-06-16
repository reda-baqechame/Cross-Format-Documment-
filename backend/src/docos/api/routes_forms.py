"""Form fields — list a document's fillable fields and fill them.

Surfaces the model's ``FieldNode`` (form template placeholders). Filling a field is an
ordinary reversible ``update_node`` on its ``value``, so it's versioned and undoable like
every other edit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import FieldInfo, FieldsResponse, FillFieldRequest, PatchResponse
from docos.db.models import Document
from docos.deps import db_session, get_orchestrator, get_provenance
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch

router = APIRouter(prefix="/documents", tags=["forms"])


@router.get("/{doc_id}/fields", response_model=FieldsResponse)
def list_fields(doc_id: str, session: Session = Depends(db_session)) -> FieldsResponse:
    _record, doc = _load_latest(session, doc_id)
    fields = [
        FieldInfo(
            node_id=n.id,
            field_name=getattr(n, "field_name", ""),
            field_kind=getattr(n, "field_kind", "text"),
            value=getattr(n, "value", None),
        )
        for n in doc.nodes.values()
        if n.type == "field"
    ]
    return FieldsResponse(doc_id=doc_id, fields=fields)


@router.post("/{doc_id}/fields", response_model=PatchResponse)
def fill_field(
    doc_id: str, body: FillFieldRequest, session: Session = Depends(db_session)
) -> PatchResponse:
    record, doc = _load_latest(session, doc_id)
    node = doc.nodes.get(body.node_id)
    if node is None or node.type != "field":
        raise HTTPException(status_code=404, detail="field not found")

    orchestrator = get_orchestrator()
    provenance = get_provenance(session)
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="update_node", target_id=body.node_id, payload={"value": body.value})],
        inverse=[],
        intent=f"fill field {getattr(node, 'field_name', body.node_id)}",
        created_at=datetime.now(UTC),
    )
    updated = orchestrator.apply(doc, patch)
    new_version_id = provenance.commit_version(updated, patch=patch)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id
    provenance.record_event(doc_id, "field.filled", actor="api", detail={"node_id": body.node_id})
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=True,
        new_version_id=new_version_id,
        intent=patch.intent,
    )
