"""The interpret path turns validated tool calls into a reversible patch.

Uses a fake LLM client that returns canned ``emit_patch`` tool calls, so the whole
AI-editing pipeline (prompt → tool call → validation → apply) is exercised with no
network or SDK dependency.
"""

from __future__ import annotations

import asyncio

from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.semantic.llm.base import LLMClient, LLMResponse
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


class FakeLLM(LLMClient):
    def __init__(self, ops: list[dict]) -> None:
        self._ops = ops
        self.seen_user: str | None = None

    async def complete(self, system, user, *, tools=None) -> LLMResponse:
        self.seen_user = user
        return LLMResponse(
            text="", tool_calls=[{"name": "emit_patch", "input": {"ops": self._ops}}]
        )


def _doc():
    return TxtAdapter().parse(b"original text")


def _run_id(doc):
    return next(n.id for n in doc.nodes.values() if n.type == "run")


def test_interpret_applies_validated_set_text():
    doc = _doc()
    rid = _run_id(doc)
    llm = FakeLLM([{"op": "set_text", "target_id": rid, "text": "rewritten by ai"}])
    orch = SemanticOrchestratorImpl(llm)

    patch = asyncio.run(orch.interpret(doc, "rewrite the text"))
    assert len(patch.patches) == 1

    updated = orch.apply(doc, patch)
    assert updated.nodes[rid].text == "rewritten by ai"
    # the run's text and id were surfaced to the model in the digest
    assert rid in (llm.seen_user or "") and "original text" in (llm.seen_user or "")


def test_interpret_drops_ops_with_unknown_target():
    doc = _doc()
    llm = FakeLLM([{"op": "set_text", "target_id": "ghost", "text": "x"}])
    orch = SemanticOrchestratorImpl(llm)

    patch = asyncio.run(orch.interpret(doc, "edit"))
    assert patch.patches == []  # invalid target rejected before reaching the engine


def test_interpret_accepts_sanitize_metadata_without_target():
    doc = _doc()
    doc.meta.custom = {"author": "Alice"}
    llm = FakeLLM([{"op": "sanitize_metadata"}])
    orch = SemanticOrchestratorImpl(llm)

    patch = asyncio.run(orch.interpret(doc, "remove my name from the metadata"))
    updated = orch.apply(doc, patch)
    assert "author" not in updated.meta.custom


def test_interpret_ignores_unknown_op():
    doc = _doc()
    llm = FakeLLM([{"op": "drop_database", "target_id": _run_id(doc)}])
    orch = SemanticOrchestratorImpl(llm)

    patch = asyncio.run(orch.interpret(doc, "do something weird"))
    assert patch.patches == []
