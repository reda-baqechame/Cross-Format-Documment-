"""User-defined workflow recipe engine (Phase H1).

A recipe is a saved, ordered list of steps over the document toolbox. Running one executes the
deterministic read/analysis tools and records the result; mutating/action steps are surfaced as
approval-gated (never auto-committed), preserving the apply→commit→audit discipline. Pure functions
here; persistence (WorkflowRecipe/WorkflowRun) lives in the route.

This generalizes the hardcoded ``business.py`` presets into stored, repeatable recipes — and gives
the agent a compile target ("describe a workflow in plain English" → a recipe).
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.semantic.agents import tools as toolbox


class RecipeStep(BaseModel):
    tool: str
    params: dict = {}


class StepResult(BaseModel):
    tool: str
    kind: str  # read | mutate | action | unknown
    status: str  # done | requires_approval | skipped | unknown_tool
    summary: str
    data: dict = {}


class RecipeRunResult(BaseModel):
    status: str  # completed | failed
    steps: list[StepResult]
    summary: str


def run_steps(doc: CanonicalDocument, steps: list[RecipeStep]) -> RecipeRunResult:
    """Execute a recipe's steps over ``doc`` (deterministic, offline). Never mutates the document.

    Read tools run and return observations. Mutate/action tools are recorded as approval-gated so
    the caller routes them through the existing preview→approve→commit paths — this engine never
    commits a change itself.
    """
    results: list[StepResult] = []
    for step in steps:
        tool = toolbox.get_tool(step.tool)
        if tool is None:
            results.append(
                StepResult(
                    tool=step.tool, kind="unknown", status="unknown_tool",
                    summary=f"No such tool '{step.tool}'.",
                )
            )
            continue
        if tool.kind == "read" and tool.run is not None:
            r = tool.run(doc)
            results.append(
                StepResult(
                    tool=tool.name, kind="read", status="done",
                    summary=r.summary, data=r.data,
                )
            )
        else:
            results.append(
                StepResult(
                    tool=tool.name, kind=tool.kind, status="requires_approval",
                    summary=(
                        f"{tool.label}: prepared, requires explicit approval before it runs "
                        "(not auto-executed by the recipe)."
                    ),
                )
            )
    done = sum(1 for r in results if r.status == "done")
    gated = sum(1 for r in results if r.status == "requires_approval")
    summary = f"{done} step(s) executed; {gated} approval-gated; {len(results)} total."
    return RecipeRunResult(status="completed", steps=results, summary=summary)
