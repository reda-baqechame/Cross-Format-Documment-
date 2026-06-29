"""Multi-document agent loop — proves cross-corpus search + doc-scoped citations, with hard rails.

Scripted fake model (no network): tools run, citations carry the right ``doc_id``, the loop never
mutates, the step budget is enforced, and the offline path returns a deterministic cited answer.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic.agents.corpus_executor import (
    run_corpus_agent,
    run_corpus_agent_loop,
)
from docos.services.semantic.corpus import CorpusDoc
from docos.services.semantic.llm.base import LLMClient, LLMResponse
from docos.services.semantic.llm.noop import LocalNoopClient


def _doc(*lines: str) -> CanonicalDocument:
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
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def _corpus() -> list[CorpusDoc]:
    a = _doc("Services Agreement with Acme.", "This agreement renews automatically each year.")
    b = _doc("Invoice from Beta LLC.", "Payment terms are net-30 days.")
    return [
        CorpusDoc(doc_id="docA", title="Acme contract", doc=a),
        CorpusDoc(doc_id="docB", title="Beta invoice", doc=b),
    ]


class ScriptedClient(LLMClient):
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


async def test_corpus_loop_searches_and_cites_correct_doc():
    client = ScriptedClient(
        [
            LLMResponse(text="", tool_calls=[_tc("search", query="renewal")]),
            LLMResponse(text="The Acme contract renews automatically.", tool_calls=[]),
        ]
    )
    run = await run_corpus_agent_loop(_corpus(), "Which contract auto-renews?", llm=client)
    assert run.used_llm is True
    assert run.answer == "The Acme contract renews automatically."
    assert {s.tool for s in run.steps} == {"search"}
    # Citations resolve to the document that actually contains the renewal clause.
    assert run.citations and all("doc_id" in c and "node_id" in c for c in run.citations)
    assert any(c["doc_id"] == "docA" for c in run.citations)
    assert all(c["doc_id"] != "docB" for c in run.citations)


async def test_corpus_loop_can_list_documents():
    client = ScriptedClient(
        [
            LLMResponse(text="", tool_calls=[_tc("list_documents")]),
            LLMResponse(text="There are two documents.", tool_calls=[]),
        ]
    )
    run = await run_corpus_agent_loop(_corpus(), "What's in the corpus?", llm=client)
    listing = [s for s in run.steps if s.tool == "list_documents"]
    assert listing and listing[0].data["documents"][0]["doc_id"] == "docA"


async def test_corpus_loop_enforces_step_budget():
    client = ScriptedClient([LLMResponse(text="", tool_calls=[_tc("search", query="x")])])
    run = await run_corpus_agent_loop(_corpus(), "loop", llm=client, max_steps=3)
    assert client.calls == 3
    assert any("step limit" in w for w in run.warnings)


async def test_corpus_offline_is_deterministic_and_cited():
    run = await run_corpus_agent(_corpus(), "payment terms", LocalNoopClient())
    assert run.used_llm is False
    assert run.steps and run.steps[0].tool == "search"
    assert "net-30" in run.answer
    assert any(c["doc_id"] == "docB" for c in run.citations)
