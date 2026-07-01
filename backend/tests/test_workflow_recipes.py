"""Workflow recipe engine (Phase H1) — save, run, and owner-scope user-defined recipes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from docos.db.models import WorkflowRecipe, WorkflowRun
from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.workflows.recipes import RecipeStep, run_steps


def _doc() -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=0)
    r = RunNode(id=new_node_id(), parent_id=p.id, text="Invoice 42. Total $100. a@b.com")
    p.children.append(r.id)
    root.children.append(p.id)
    doc.add_node(p)
    doc.add_node(r)
    return doc


def test_run_steps_executes_read_tools_and_gates_mutations():
    result = run_steps(
        _doc(),
        [
            RecipeStep(tool="classify"),
            RecipeStep(tool="sensitive_scan"),
            RecipeStep(tool="redact_pii"),  # mutate → approval-gated, not auto-run
        ],
    )
    by_tool = {s.tool: s for s in result.steps}
    assert by_tool["classify"].status == "done"
    assert by_tool["sensitive_scan"].status == "done"
    assert by_tool["redact_pii"].status == "requires_approval"
    assert result.status == "completed"


def test_run_steps_handles_unknown_tool():
    result = run_steps(_doc(), [RecipeStep(tool="does_not_exist")])
    assert result.steps[0].status == "unknown_tool"


def test_recipe_crud_and_run_endpoint(client):
    created = client.post(
        "/recipes",
        json={
            "name": "Intake triage",
            "steps": [{"tool": "classify"}, {"tool": "extract"}],
        },
    )
    assert created.status_code == 200
    recipe_id = created.json()["id"]

    listed = client.get("/recipes").json()
    assert any(r["id"] == recipe_id for r in listed)

    doc_id = client.post(
        "/documents",
        files={"file": ("d.txt", b"Invoice 42. Total due $100.", "text/plain")},
    ).json()["doc_id"]

    run = client.post(f"/recipes/{recipe_id}/run", json={"doc_id": doc_id})
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["run_id"].startswith("wfr_")
    assert {s["tool"] for s in body["steps"]} == {"classify", "extract"}
    assert all(s["status"] == "done" for s in body["steps"])

    history = client.get(f"/recipes/{recipe_id}/runs")
    assert history.status_code == 200
    assert history.json()[0]["id"] == body["run_id"]

    detail = client.get(f"/recipes/{recipe_id}/runs/{body['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["document_id"] == doc_id

    updated = client.patch(
        f"/recipes/{recipe_id}",
        json={"name": "Intake and privacy", "steps": [{"tool": "sensitive_scan"}]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Intake and privacy"
    assert updated.json()["steps"] == [{"tool": "sensitive_scan", "params": {}}]

    deleted = client.delete(f"/recipes/{recipe_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get(f"/recipes/{recipe_id}").status_code == 404


def test_run_unknown_recipe_is_404(client):
    doc_id = client.post("/documents", files={"file": ("d.txt", b"hi", "text/plain")}).json()[
        "doc_id"
    ]
    res = client.post("/recipes/wf_missing/run", json={"doc_id": doc_id})
    assert res.status_code == 404


def test_recipe_tools_catalog_marks_every_non_read_tool_approval_gated(client):
    response = client.get("/recipe-tools")
    assert response.status_code == 200
    tools = response.json()
    assert {tool["name"] for tool in tools} >= {"classify", "extract", "redact_pii"}
    assert all(tool["requires_approval"] for tool in tools if tool["kind"] != "read")


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"name": "Bad tool", "steps": [{"tool": "shell_exec"}]}, "unknown recipe tool"),
        (
            {"name": "Fake trigger", "trigger": "on_upload", "steps": [{"tool": "classify"}]},
            "Input should be 'manual'",
        ),
        ({"name": "No steps", "steps": []}, "at least 1 item"),
        (
            {"name": "Too many", "steps": [{"tool": "classify"}] * 33},
            "at most 32 items",
        ),
        (
            {"name": "Huge params", "steps": [{"tool": "classify", "params": {"x": "a" * 9000}}]},
            "step params must be at most 8192 bytes",
        ),
    ],
)
def test_recipe_creation_rejects_unsupported_or_oversized_inputs(client, payload, detail):
    response = client.post("/recipes", json=payload)
    assert response.status_code == 422
    assert detail in response.text


def test_recipe_update_rejects_unknown_tools_without_changing_recipe(client):
    recipe_id = client.post(
        "/recipes", json={"name": "Safe", "steps": [{"tool": "classify"}]}
    ).json()["id"]

    response = client.patch(f"/recipes/{recipe_id}", json={"steps": [{"tool": "does_not_exist"}]})
    assert response.status_code == 422
    assert client.get(f"/recipes/{recipe_id}").json()["steps"][0]["tool"] == "classify"


def test_anonymous_recipes_and_runs_are_cross_session_isolated(make_client):
    alice = make_client()
    bob = make_client()
    recipe_id = alice.post(
        "/recipes", json={"name": "Alice only", "steps": [{"tool": "classify"}]}
    ).json()["id"]
    doc_id = alice.post(
        "/documents", files={"file": ("a.txt", b"Alice invoice", "text/plain")}
    ).json()["doc_id"]
    run_id = alice.post(f"/recipes/{recipe_id}/run", json={"doc_id": doc_id}).json()["run_id"]

    assert bob.get("/recipes").json() == []
    assert bob.get(f"/recipes/{recipe_id}").status_code == 404
    assert bob.patch(f"/recipes/{recipe_id}", json={"name": "Stolen"}).status_code == 404
    assert bob.delete(f"/recipes/{recipe_id}").status_code == 404
    assert bob.post(f"/recipes/{recipe_id}/run", json={"doc_id": doc_id}).status_code == 404
    assert bob.get(f"/recipes/{recipe_id}/runs").status_code == 404
    assert bob.get(f"/recipes/{recipe_id}/runs/{run_id}").status_code == 404

    assert alice.get(f"/recipes/{recipe_id}").status_code == 200
    assert alice.get(f"/recipes/{recipe_id}/runs/{run_id}").status_code == 200


def test_register_claims_recipe_and_run_for_authenticated_cross_session_access(make_client, db):
    first_session = make_client()
    recipe_id = first_session.post(
        "/recipes", json={"name": "Claim me", "steps": [{"tool": "classify"}]}
    ).json()["id"]
    doc_id = first_session.post(
        "/documents", files={"file": ("a.txt", b"Invoice 42", "text/plain")}
    ).json()["doc_id"]
    run_id = first_session.post(f"/recipes/{recipe_id}/run", json={"doc_id": doc_id}).json()[
        "run_id"
    ]

    email = f"recipe_{uuid.uuid4().hex[:10]}@example.com"
    registered = first_session.post(
        "/auth/register", json={"email": email, "password": "password123"}
    )
    assert registered.status_code == 200, registered.text
    claimed = registered.json()["claimed"]
    assert claimed["workflow_recipes"] == 1
    assert claimed["workflow_runs"] == 1

    recipe = db.scalar(select(WorkflowRecipe).where(WorkflowRecipe.id == recipe_id))
    run = db.scalar(select(WorkflowRun).where(WorkflowRun.id == run_id))
    assert recipe is not None and recipe.owner_user_id == registered.json()["user"]["id"]
    assert run is not None and run.owner_user_id == registered.json()["user"]["id"]

    second_session = make_client()
    login = second_session.post("/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    assert second_session.get(f"/recipes/{recipe_id}").status_code == 200
    assert second_session.get(f"/recipes/{recipe_id}/runs/{run_id}").status_code == 200

    other_user = make_client()
    other_user.post(
        "/auth/register",
        json={
            "email": f"other_{uuid.uuid4().hex[:10]}@example.com",
            "password": "password123",
        },
    )
    assert other_user.get(f"/recipes/{recipe_id}").status_code == 404
    assert other_user.get(f"/recipes/{recipe_id}/runs/{run_id}").status_code == 404


def test_legacy_unknown_tool_is_listed_and_safely_reported(client, db):
    created = client.post(
        "/recipes", json={"name": "Legacy", "steps": [{"tool": "classify"}]}
    ).json()
    recipe = db.get(WorkflowRecipe, created["id"])
    assert recipe is not None
    recipe.steps = [{"tool": "retired_tool", "params": {}}]
    db.commit()

    listed = client.get(f"/recipes/{created['id']}")
    assert listed.status_code == 200
    assert listed.json()["steps"][0]["tool"] == "retired_tool"

    doc_id = client.post(
        "/documents", files={"file": ("legacy.txt", b"legacy", "text/plain")}
    ).json()["doc_id"]
    run = client.post(f"/recipes/{created['id']}/run", json={"doc_id": doc_id})
    assert run.status_code == 200
    assert run.json()["steps"][0]["status"] == "unknown_tool"
