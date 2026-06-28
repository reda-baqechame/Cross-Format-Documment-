"""Workflow recipe engine (Phase H1) — save, run, and owner-scope user-defined recipes."""

from __future__ import annotations

from datetime import UTC, datetime

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
    assert {s["tool"] for s in body["steps"]} == {"classify", "extract"}
    assert all(s["status"] == "done" for s in body["steps"])


def test_run_unknown_recipe_is_404(client):
    doc_id = client.post(
        "/documents", files={"file": ("d.txt", b"hi", "text/plain")}
    ).json()["doc_id"]
    res = client.post("/recipes/wf_missing/run", json={"doc_id": doc_id})
    assert res.status_code == 404
