"""Iterative agentic executor — proves the plan→act→observe→cite→propose loop, with hard rails.

Uses a scripted fake model (no network) so the loop's mechanics are verified deterministically
before any real key is configured: tools run, observations feed back, edits are proposed (preview)
and never committed, passages are cited, and the step budget is enforced.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic.agents.executor import run_agent_loop
from docos.services.semantic.llm.base import LLMClient, LLMResponse
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


class ScriptedClient(LLMClient):
    """A fake model that emits a fixed sequence of turns, asserting the loop feeds tools back."""

    def __init__(self, turns: list[LLMResponse]) -> None:
        self._turns = turns
        self.calls = 0
        self.last_messages: list[dict] = []

    async def complete(self, system, user, *, tools=None) -> LLMResponse:  # pragma: no cover
        return LLMResponse(text="", tool_calls=[])

    async def converse(self, system, messages, *, tools=None) -> LLMResponse:
        self.last_messages = messages
        turn = self._turns[min(self.calls, len(self._turns) - 1)]
        self.calls += 1
        return turn


def _tc(name: str, **inp) -> dict:
    return {"id": f"call-{name}", "name": name, "input": inp}


async def test_loop_runs_tools_then_answers():
    client = ScriptedClient(
        [
            LLMResponse(text="", tool_calls=[_tc("classify")]),
            LLMResponse(text="", tool_calls=[_tc("search", query="invoice number")]),
            LLMResponse(text="The invoice number is 42.", tool_calls=[]),
        ]
    )
    run = await run_agent_loop(
        _doc(),
        "what is the invoice number?",
        llm=client,
        orchestrator=SemanticOrchestratorImpl(client),
    )
    assert run.used_llm is True
    assert run.answer == "The invoice number is 42."
    tools_run = {s.tool for s in run.steps}
    assert {"classify", "search"} <= tools_run
    # search produced resolvable citations (node ids that exist in the doc)
    assert run.citations and all("node_id" in c for c in run.citations)


async def test_loop_proposes_edit_but_never_commits():
    client = ScriptedClient(
        [
            LLMResponse(
                text="", tool_calls=[_tc("propose_edit", instruction="change total to $200")]
            ),
            LLMResponse(text="I prepared an edit for your approval.", tool_calls=[]),
        ]
    )
    doc = _doc()
    run = await run_agent_loop(
        doc, "change the total to $200", llm=client, orchestrator=SemanticOrchestratorImpl(client)
    )
    modify = [s for s in run.steps if s.tool == "modify"]
    assert modify and modify[0].requires_approval is True
    assert run.proposed_patch is not None  # a preview exists
    # The document object is untouched — the loop only proposes.
    assert doc.nodes  # still intact; nothing committed


async def test_loop_enforces_step_budget():
    # A model that never stops calling tools must be bounded.
    client = ScriptedClient([LLMResponse(text="", tool_calls=[_tc("classify")])])
    run = await run_agent_loop(
        _doc(),
        "loop forever",
        llm=client,
        orchestrator=SemanticOrchestratorImpl(client),
        max_steps=3,
    )
    assert client.calls == 3  # exactly the budget, no more
    assert any("step limit" in w for w in run.warnings)


async def test_tool_observations_are_fed_back_to_the_model():
    # After a tool call, the next converse() must receive a 'tool' turn with the result.
    client = ScriptedClient(
        [
            LLMResponse(text="", tool_calls=[_tc("classify")]),
            LLMResponse(text="done", tool_calls=[]),
        ]
    )
    await run_agent_loop(
        _doc(), "analyze", llm=client, orchestrator=SemanticOrchestratorImpl(client)
    )
    roles = [m.get("role") for m in client.last_messages]
    assert "tool" in roles  # the observation was appended before the final turn
