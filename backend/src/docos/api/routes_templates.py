"""Templates & styles library.

Save any open document's structure as a reusable template, then stamp out fresh
documents from it. Instantiation produces a fully independent document (new ids, new
version lineage) via ``services/templates`` and persists it like any uploaded document,
so every downstream capability (edit, export, sign, …) works on it unchanged.
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.session import Actor, get_actor
from docos.db.models import Document, Template
from docos.deps import db_session, get_provenance
from docos.services.templates import library

router = APIRouter(tags=["templates"])


class SaveTemplateRequest(BaseModel):
    name: str
    description: str | None = None


class InstantiateRequest(BaseModel):
    title: str | None = None


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str | None
    source_format: str
    variables: list[str]
    created_at: str


class TemplateListResponse(BaseModel):
    templates: list[TemplateSummary]


class InstantiateResponse(BaseModel):
    doc_id: str
    version_id: str
    template_id: str


_VARIABLE = re.compile(r"\{\{\s*([A-Za-z][A-Za-z0-9 _.-]{1,60})\s*\}\}")


def _variables(model: dict) -> list[str]:
    found: set[str] = set()
    nodes = model.get("nodes") if isinstance(model, dict) else None
    if not isinstance(nodes, dict):
        return []
    for raw in nodes.values():
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "field" and raw.get("field_name"):
            found.add(str(raw["field_name"]).strip())
        text = str(raw.get("text") or "")
        for match in _VARIABLE.finditer(text):
            found.add(match.group(1).strip())
    return sorted(v for v in found if v)


def _summary(t: Template) -> TemplateSummary:
    return TemplateSummary(
        id=t.id,
        name=t.name,
        description=t.description,
        source_format=t.source_format,
        variables=_variables(t.model),
        created_at=t.created_at.isoformat(),
    )


def _owns_template(template: Template, actor: Actor) -> bool:
    if template.owner_session_id is not None and template.owner_session_id == actor.session_id:
        return True
    return (
        template.owner_user_id is not None
        and actor.user_id is not None
        and template.owner_user_id == actor.user_id
    )


def _template_filters(actor: Actor):
    clauses = [Template.owner_session_id == actor.session_id]
    if actor.user_id is not None:
        clauses.append(Template.owner_user_id == actor.user_id)
    return or_(*clauses)


@router.post("/documents/{doc_id}/save-as-template", response_model=TemplateSummary)
def save_as_template(
    doc_id: str,
    body: SaveTemplateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> TemplateSummary:
    record, doc = _load_latest(session, doc_id, actor)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="template name is required")

    template = Template(
        id=f"tpl_{uuid.uuid4().hex[:12]}",
        name=name,
        description=(body.description or None),
        source_doc_id=doc_id,
        source_format=record.source_format,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        model=library.snapshot(doc),
    )
    session.add(template)
    get_provenance(session).record_event(
        doc_id, "template.saved", actor="api", detail={"template_id": template.id, "name": name}
    )
    session.commit()
    return _summary(template)


@router.get("/templates", response_model=TemplateListResponse)
def list_templates(
    session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> TemplateListResponse:
    rows = session.scalars(
        select(Template).where(_template_filters(actor)).order_by(Template.created_at.desc())
    ).all()
    return TemplateListResponse(templates=[_summary(t) for t in rows])


@router.post("/templates/{template_id}/instantiate", response_model=InstantiateResponse)
def instantiate_template(
    template_id: str,
    body: InstantiateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> InstantiateResponse:
    template = session.get(Template, template_id)
    if template is None or not _owns_template(template, actor):
        raise HTTPException(status_code=404, detail="template not found")

    doc = library.instantiate(template.model, title=body.title)
    record = Document(
        id=doc.doc_id,
        title=doc.meta.title,
        source_format=doc.meta.source_format,
        source_mime=doc.meta.source_mime,
        blob_key="",  # born-digital from a template — no original upload bytes
        owner_session_id=actor.session_id,
    )
    session.add(record)
    session.flush()

    provenance = get_provenance(session)
    version_id = provenance.commit_version(doc)
    record.current_version_id = version_id
    provenance.record_event(
        doc.doc_id,
        "document.from_template",
        actor="api",
        detail={"template_id": template_id},
    )
    session.commit()
    return InstantiateResponse(doc_id=doc.doc_id, version_id=version_id, template_id=template_id)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> None:
    template = session.get(Template, template_id)
    if template is None or not _owns_template(template, actor):
        raise HTTPException(status_code=404, detail="template not found")
    session.delete(template)
    session.commit()
