"""Owner-scoped workflow recipe CRUD, execution, and run history.

The initial trigger contract is deliberately manual-only. Read tools execute deterministically;
mutating and side-effecting tools remain approval-gated and are never committed by this engine.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from docos.api._corpus import load_corpus
from docos.api.access import owner_clause
from docos.api.ratelimit import enforce_op_rate
from docos.api.session import Actor, get_actor
from docos.db.models import WorkflowRecipe, WorkflowRun
from docos.deps import db_session
from docos.services.semantic.agents.tools import all_tools, get_tool
from docos.services.workflows.recipes import RecipeRunResult, RecipeStep, StepResult, run_steps

router = APIRouter(prefix="/recipes", tags=["workflows"])
tools_router = APIRouter(tags=["workflows"])

MAX_RECIPE_STEPS = 32
MAX_RECIPE_PAYLOAD_BYTES = 32768


class RecipeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    trigger: Literal["manual"] = "manual"
    steps: list[RecipeStep] = Field(min_length=1, max_length=MAX_RECIPE_STEPS)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @model_validator(mode="after")
    def limit_payload(self) -> RecipeCreateRequest:
        _validate_recipe_payload(self.steps)
        return self


class RecipeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    trigger: Literal["manual"] | None = None
    steps: list[RecipeStep] | None = Field(default=None, min_length=1, max_length=MAX_RECIPE_STEPS)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @model_validator(mode="after")
    def limit_payload(self) -> RecipeUpdateRequest:
        if self.steps is not None:
            _validate_recipe_payload(self.steps)
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class RecipeOut(BaseModel):
    id: str
    name: str
    trigger: str
    steps: list[RecipeStep]
    created_at: datetime
    updated_at: datetime


class RecipeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1, max_length=128)


class RecipeRunOut(BaseModel):
    id: str
    recipe_id: str
    document_id: str | None
    status: str
    steps: list[StepResult]
    summary: str
    created_at: datetime


class RecipeToolOut(BaseModel):
    name: str
    kind: str
    label: str
    description: str
    requires_approval: bool
    destructive: bool


def _validate_recipe_payload(steps: list[RecipeStep]) -> None:
    encoded = json.dumps(
        [step.model_dump() for step in steps], ensure_ascii=False, separators=(",", ":")
    ).encode()
    if len(encoded) > MAX_RECIPE_PAYLOAD_BYTES:
        raise ValueError(f"recipe steps must be at most {MAX_RECIPE_PAYLOAD_BYTES} bytes")


def _validate_tools(steps: list[RecipeStep]) -> None:
    unknown = sorted({step.tool for step in steps if get_tool(step.tool) is None})
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown recipe tool(s): {', '.join(unknown)}",
        )


def _stored_steps(raw_steps: list | None) -> list[RecipeStep]:
    """Best-effort decoding for records written before strict recipe validation existed."""
    steps: list[RecipeStep] = []
    for raw in raw_steps or []:
        if not isinstance(raw, dict):
            continue
        tool = raw.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        params = raw.get("params")
        try:
            steps.append(RecipeStep(tool=tool, params=params if isinstance(params, dict) else {}))
        except ValueError:
            # Oversized or malformed legacy data is ignored rather than crashing list/run routes.
            continue
    return steps


def _stored_results(raw_results: list | None) -> list[StepResult]:
    results: list[StepResult] = []
    for raw in raw_results or []:
        if not isinstance(raw, dict):
            continue
        try:
            results.append(StepResult(**raw))
        except ValueError:
            continue
    return results


def _result_summary(steps: list[StepResult]) -> str:
    done = sum(step.status == "done" for step in steps)
    gated = sum(step.status == "requires_approval" for step in steps)
    return f"{done} step(s) executed; {gated} approval-gated; {len(steps)} total."


def _to_out(recipe: WorkflowRecipe) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        trigger=recipe.trigger,
        steps=_stored_steps(recipe.steps),
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def _run_out(run: WorkflowRun) -> RecipeRunOut:
    steps = _stored_results(run.results)
    return RecipeRunOut(
        id=run.id,
        recipe_id=run.recipe_id,
        document_id=run.document_id,
        status=run.status,
        steps=steps,
        summary=_result_summary(steps),
        created_at=run.created_at,
    )


def _get_owned_recipe(session: Session, recipe_id: str, actor: Actor) -> WorkflowRecipe:
    recipe = session.scalar(
        select(WorkflowRecipe).where(
            WorkflowRecipe.id == recipe_id,
            owner_clause(WorkflowRecipe.owner_session_id, WorkflowRecipe.owner_user_id, actor),
        )
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="recipe not found")
    return recipe


@tools_router.get("/recipe-tools", response_model=list[RecipeToolOut])
def list_recipe_tools() -> list[RecipeToolOut]:
    return [
        RecipeToolOut(
            name=tool.name,
            kind=tool.kind,
            label=tool.label,
            description=tool.description,
            requires_approval=tool.requires_approval or tool.kind != "read",
            destructive=tool.destructive,
        )
        for tool in all_tools()
    ]


@router.post("", response_model=RecipeOut)
def create_recipe(
    body: RecipeCreateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RecipeOut:
    _validate_tools(body.steps)
    recipe = WorkflowRecipe(
        id=f"wf_{uuid.uuid4().hex[:12]}",
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        name=body.name,
        trigger="manual",
        steps=[step.model_dump() for step in body.steps],
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return _to_out(recipe)


@router.get("", response_model=list[RecipeOut])
def list_recipes(
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> list[RecipeOut]:
    stmt = select(WorkflowRecipe).where(
        owner_clause(WorkflowRecipe.owner_session_id, WorkflowRecipe.owner_user_id, actor)
    )
    return [
        _to_out(recipe)
        for recipe in session.scalars(stmt.order_by(WorkflowRecipe.created_at.desc()))
    ]


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(
    recipe_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RecipeOut:
    return _to_out(_get_owned_recipe(session, recipe_id, actor))


@router.patch("/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: str,
    body: RecipeUpdateRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RecipeOut:
    recipe = _get_owned_recipe(session, recipe_id, actor)
    if body.steps is not None:
        _validate_tools(body.steps)
        recipe.steps = [step.model_dump() for step in body.steps]
    if body.name is not None:
        recipe.name = body.name
    if body.trigger is not None:
        recipe.trigger = "manual"
    session.commit()
    session.refresh(recipe)
    return _to_out(recipe)


@router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> dict[str, bool]:
    recipe = _get_owned_recipe(session, recipe_id, actor)
    session.execute(delete(WorkflowRun).where(WorkflowRun.recipe_id == recipe.id))
    session.delete(recipe)
    session.commit()
    return {"ok": True}


@router.post("/{recipe_id}/run", response_model=RecipeRunResult)
def run_recipe(
    recipe_id: str,
    body: RecipeRunRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> RecipeRunResult:
    recipe = _get_owned_recipe(session, recipe_id, actor)
    corpus = load_corpus(
        session,
        [body.doc_id],
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
    )
    if not corpus:
        raise HTTPException(status_code=404, detail="document not found")

    result = run_steps(corpus[0].doc, _stored_steps(recipe.steps))
    run = WorkflowRun(
        id=f"wfr_{uuid.uuid4().hex[:12]}",
        recipe_id=recipe.id,
        document_id=body.doc_id,
        owner_session_id=actor.session_id,
        owner_user_id=actor.user_id,
        status=result.status,
        results=[step.model_dump() for step in result.steps],
    )
    session.add(run)
    session.commit()
    return result.model_copy(
        update={"run_id": run.id, "recipe_id": recipe.id, "document_id": body.doc_id}
    )


@router.get("/{recipe_id}/runs", response_model=list[RecipeRunOut])
def list_recipe_runs(
    recipe_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> list[RecipeRunOut]:
    _get_owned_recipe(session, recipe_id, actor)
    stmt = (
        select(WorkflowRun)
        .where(
            WorkflowRun.recipe_id == recipe_id,
            owner_clause(WorkflowRun.owner_session_id, WorkflowRun.owner_user_id, actor),
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(limit)
    )
    return [_run_out(run) for run in session.scalars(stmt)]


@router.get("/{recipe_id}/runs/{run_id}", response_model=RecipeRunOut)
def get_recipe_run(
    recipe_id: str,
    run_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> RecipeRunOut:
    _get_owned_recipe(session, recipe_id, actor)
    run = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.recipe_id == recipe_id,
            owner_clause(WorkflowRun.owner_session_id, WorkflowRun.owner_user_id, actor),
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="recipe run not found")
    return _run_out(run)
