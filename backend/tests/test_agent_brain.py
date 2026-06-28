"""The agentic document brain: composes plan + read tools + a modify *preview* (never commits)."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic.agents import run_agent
from docos.services.semantic.agents import tools as toolbox
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def _doc(text: str = "Invoice number 42. Total due $100. Email a@b.com.") -> CanonicalDocument:
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
    r = RunNode(id=new_node_id(), parent_id=p.id, text=text)
    p.children.append(r.id)
    root.children.append(p.id)
    doc.add_node(p)
    doc.add_node(r)
    return doc


def _orchestrator() -> SemanticOrchestratorImpl:
    return SemanticOrchestratorImpl(LocalNoopClient())


async def test_agent_runs_read_tools_offline():
    run = await run_agent(_doc(), "analyze this document", orchestrator=_orchestrator())
    tools_run = {s.tool for s in run.steps}
    assert {"classify", "extract", "intelligence"} <= tools_run
    assert run.classification  # non-empty type label
    # Read-only goal proposes no edits.
    assert run.proposed_patch is None
    assert run.used_llm is False  # noop provider


async def test_agent_proposes_but_does_not_commit_on_modify_goal():
    run = await run_agent(_doc(), "change the total to $200", orchestrator=_orchestrator())
    modify = [s for s in run.steps if s.tool == "modify"]
    assert modify, "a modify goal must add a modify step"
    assert modify[0].requires_approval is True
    # Offline noop yields an empty proposal (honest), and the agent never commits regardless.
    assert run.proposed_patch is not None
    assert run.proposed_patch.change_count == 0


async def test_agent_adds_sensitive_scan_on_redaction_goal():
    run = await run_agent(_doc(), "redact all PII", orchestrator=_orchestrator())
    assert any(s.tool == "sensitive_scan" for s in run.steps)


def test_tool_registry_shape():
    # Read tools carry a runner; mutate/action tools are approval-described, not auto-run.
    reads = toolbox.read_tools()
    assert {"classify", "extract", "intelligence", "sensitive_scan"} <= set(reads)
    assert all(t.run is not None for t in reads.values())
    redact = toolbox.get_tool("redact_pii")
    assert redact is not None and redact.destructive and redact.requires_approval


def test_agent_endpoint_end_to_end(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("d.txt", b"Invoice 42. Total due $100. Contact a@b.com.", "text/plain")},
    ).json()["doc_id"]

    res = client.post(f"/documents/{doc_id}/agent", json={"goal": "analyze and extract fields"})
    assert res.status_code == 200
    body = res.json()
    assert body["classification"]
    tools_run = {s["tool"] for s in body["steps"]}
    assert {"classify", "extract"} <= tools_run
    # A read goal proposes no edits (and the endpoint never commits, regardless of goal).
    assert body["proposed_patch"] is None
    assert body["used_llm"] is False  # offline test env
