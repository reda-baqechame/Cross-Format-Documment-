"""Form fields — list a document's fillable fields and fill them.

Surfaces the model's ``FieldNode`` (form template placeholders). Filling a field is an
ordinary reversible ``update_node`` on its ``value``, so it's versioned and undoable like
every other edit.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    CreateFieldRequest,
    DetectFieldsResponse,
    FieldInfo,
    FieldsResponse,
    FillFieldRequest,
    PatchResponse,
    UpdateFieldRequest,
)
from docos.api.session import Actor, get_actor
from docos.db.models import Document
from docos.deps import db_session, get_orchestrator, get_provenance
from docos.model.ids import new_node_id, new_patch_id
from docos.model.nodes import FieldNode
from docos.model.patch import Patch, ReversiblePatch

router = APIRouter(prefix="/documents", tags=["forms"])

_FIELD_UPDATE_KEYS = (
    "field_name",
    "field_kind",
    "value",
    "required",
    "placeholder",
    "help_text",
    "options",
    "validation_pattern",
    "default_value",
)

_BLANK_FIELD = re.compile(
    r"([A-Za-z][A-Za-z0-9 /._#-]{1,50})\s*[:\-]\s*(?:_{2,}|\[\s*\]|\(\s*\)|\.{3,})"
)


def _field_info(node) -> FieldInfo:
    return FieldInfo(
        node_id=node.id,
        field_name=getattr(node, "field_name", ""),
        field_kind=getattr(node, "field_kind", "text"),
        value=getattr(node, "value", None),
        required=getattr(node, "required", False),
        placeholder=getattr(node, "placeholder", None),
        help_text=getattr(node, "help_text", None),
        options=list(getattr(node, "options", [])),
        validation_pattern=getattr(node, "validation_pattern", None),
        default_value=getattr(node, "default_value", None),
    )


def _field_node(body: CreateFieldRequest, parent_id: str) -> FieldNode:
    return FieldNode(
        id=new_node_id("field"),
        parent_id=parent_id,
        field_name=body.field_name,
        field_kind=body.field_kind,
        value=body.value,
        required=body.required,
        placeholder=body.placeholder,
        help_text=body.help_text,
        options=body.options,
        validation_pattern=body.validation_pattern,
        default_value=body.default_value,
    )


def _patch_response(doc_id: str, patch: ReversiblePatch, version_id: str | None) -> PatchResponse:
    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=bool(patch.patches),
        new_version_id=version_id,
        intent=patch.intent,
    )


@router.get("/{doc_id}/fields", response_model=FieldsResponse)
def list_fields(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> FieldsResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    fields = [_field_info(n) for n in doc.nodes.values() if n.type == "field"]
    return FieldsResponse(doc_id=doc_id, fields=fields)


@router.post("/{doc_id}/fields/detect", response_model=DetectFieldsResponse)
def detect_fields(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> DetectFieldsResponse:
    """Convert visible blanks like ``Name: ______`` into real fillable fields."""
    _record, doc = _load_latest(session, doc_id, actor)
    existing = {
        getattr(n, "field_name", "").strip().lower()
        for n in doc.nodes.values()
        if n.type == "field"
    }
    ops: list[Patch] = []
    per_parent_counts: dict[str, int] = {}
    for node in doc.walk():
        if node.type != "run":
            continue
        text = getattr(node, "text", "") or ""
        parent_id = node.parent_id
        if not parent_id or parent_id not in doc.nodes:
            continue
        for match in _BLANK_FIELD.finditer(text):
            label = match.group(1).strip(" :-")
            key = label.lower()
            if not label or key in existing:
                continue
            existing.add(key)
            siblings = doc.nodes[parent_id].children
            base_index = siblings.index(node.id) + 1 if node.id in siblings else len(siblings)
            offset = per_parent_counts.get(parent_id, 0)
            per_parent_counts[parent_id] = offset + 1
            field = FieldNode(
                id=new_node_id("field"),
                parent_id=parent_id,
                field_name=label,
                field_kind="text",
                placeholder=label,
                required=True,
            )
            ops.append(
                Patch(
                    op="add_node",
                    payload={
                        "node": field.model_dump(),
                        "parent_id": parent_id,
                        "index": base_index + offset,
                    },
                )
            )

    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent=f"detect {len(ops)} fillable field(s)",
        created_at=datetime.now(UTC),
    )
    version_id, _updated = apply_and_commit(
        session,
        doc_id,
        doc,
        patch,
        actor=actor,
        event="fields.detected",
        detail={"detected": len(ops)},
    )
    return DetectFieldsResponse(
        doc_id=doc_id, detected=len(ops), patch=_patch_response(doc_id, patch, version_id)
    )


@router.post("/{doc_id}/fields/create", response_model=PatchResponse)
def create_field(
    doc_id: str,
    body: CreateFieldRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> PatchResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    parent_id = body.parent_id or doc.root_id
    if parent_id not in doc.nodes:
        raise HTTPException(status_code=422, detail="field parent not found")
    field = _field_node(body, parent_id)
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(
                op="add_node",
                payload={
                    "node": field.model_dump(),
                    "parent_id": parent_id,
                    "index": body.index,
                },
            )
        ],
        inverse=[],
        intent=f"create field {body.field_name}",
        created_at=datetime.now(UTC),
    )
    version_id, _updated = apply_and_commit(
        session,
        doc_id,
        doc,
        patch,
        actor=actor,
        event="field.created",
        detail={"field_name": body.field_name},
    )
    return _patch_response(doc_id, patch, version_id)


@router.patch("/{doc_id}/fields/{field_id}", response_model=PatchResponse)
def update_field(
    doc_id: str,
    field_id: str,
    body: UpdateFieldRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> PatchResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    node = doc.nodes.get(field_id)
    if node is None or node.type != "field":
        raise HTTPException(status_code=404, detail="field not found")
    payload = {
        key: value for key in _FIELD_UPDATE_KEYS if (value := getattr(body, key)) is not None
    }
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="update_node", target_id=field_id, payload=payload)] if payload else [],
        inverse=[],
        intent=f"update field {getattr(node, 'field_name', field_id)}",
        created_at=datetime.now(UTC),
    )
    version_id, _updated = apply_and_commit(
        session,
        doc_id,
        doc,
        patch,
        actor=actor,
        event="field.updated",
        detail={"node_id": field_id},
    )
    return _patch_response(doc_id, patch, version_id)


@router.delete("/{doc_id}/fields/{field_id}", response_model=PatchResponse)
def delete_field(
    doc_id: str,
    field_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> PatchResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    node = doc.nodes.get(field_id)
    if node is None or node.type != "field":
        raise HTTPException(status_code=404, detail="field not found")
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="remove_node", target_id=field_id)],
        inverse=[],
        intent=f"delete field {getattr(node, 'field_name', field_id)}",
        created_at=datetime.now(UTC),
    )
    version_id, _updated = apply_and_commit(
        session,
        doc_id,
        doc,
        patch,
        actor=actor,
        event="field.deleted",
        detail={"node_id": field_id},
    )
    return _patch_response(doc_id, patch, version_id)


@router.post("/{doc_id}/fields", response_model=PatchResponse)
def fill_field(
    doc_id: str,
    body: FillFieldRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> PatchResponse:
    record, doc = _load_latest(session, doc_id, actor)
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
