"""Workflow recipe endpoints (Phase H1) — save, list, and run user-defined workflows.

Additive + owner-scoped. Creating a recipe stores an ordered list of toolbox steps; running one
executes the deterministic read/analysis tools over the document and records a ``WorkflowRun``.
Mutating/action steps are surfaced as approval-gated — the engine never commits a change itself.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.db.models import WorkflowRecipe, WorkflowRun
from docos.deps import db_session
from docos.services.workflows.recipes import RecipeRunResult, RecipeStep, run_steps

router = APIRouter(prefix="/recipes", tags=["workflows"])


class RecipeCreateRequest(BaseModel):
    name: str
    trigger: str = "manual"
    steps: list[RecipeStep]


class RecipeOut(BaseModel):
    id: str
    name: str
    trigger: str
    steps: list[RecipeStep]


class RecipeRunRequest(BaseModel):
    doc_id: str


def _to_out(r: WorkflowRecipe) -> RecipeOut:
    return RecipeOut(
        id=r.id,
        name=r.name,
        trigger=r.trigger,
        steps=[RecipeStep(**s) for s in (r.steps or [])],
    )


@router.post("", response_model=RecipeOut)
def create_recipe(
    body: RecipeCreateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RecipeOut:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    if not body.steps:
        raise HTTPException(status_code=422, detail="at least one step is required")
    recipe = WorkflowRecipe(
        id=f"wf_{uuid.uuid4().hex[:12]}",
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        name=body.name.strip(),
        trigger=body.trigger,
        steps=[s.model_dump() for s in body.steps],
    )
    session.add(recipe)
    session.commit()
    return _to_out(recipe)


@router.get("", response_model=list[RecipeOut])
def list_recipes(
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> list[RecipeOut]:
    stmt = select(WorkflowRecipe).where(
        or_(
            WorkflowRecipe.owner_session_id == actor.session_id,
            WorkflowRecipe.owner_user_id == actor.user_id,
        )
    )
    return [_to_out(r) for r in session.scalars(stmt.order_by(WorkflowRecipe.created_at.desc()))]


@router.post("/{recipe_id}/run", response_model=RecipeRunResult)
def run_recipe(
    recipe_id: str,
    body: RecipeRunRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RecipeRunResult:
    recipe = session.get(WorkflowRecipe, recipe_id)
    if recipe is None or (
        recipe.owner_session_id != actor.session_id
        and recipe.owner_user_id != actor.user_id
    ):
        raise HTTPException(status_code=404, detail="recipe not found")
    corpus = load_corpus(
        session,
        [body.doc_id],
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="document not found")

    steps = [RecipeStep(**s) for s in (recipe.steps or [])]
    result = run_steps(corpus[0].doc, steps)

    session.add(
        WorkflowRun(
            id=f"wfr_{uuid.uuid4().hex[:12]}",
            recipe_id=recipe.id,
            document_id=body.doc_id,
            owner_session_id=actor.session_id,
            owner_user_id=actor.user_id,
            status=result.status,
            results=[s.model_dump() for s in result.steps],
        )
    )
    session.commit()
    return result
