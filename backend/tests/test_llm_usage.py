"""Token-usage metering: providers report usage; the agent loop tallies it across turns."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic.agents.executor import run_agent_loop
from docos.services.semantic.llm.base import LLMClient, LLMResponse, merge_usage
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def test_merge_usage_sums_keywise():
    assert merge_usage(None, None) is None
    assert merge_usage(None, {"input_tokens": 5}) == {"input_tokens": 5}
    assert merge_usage({"input_tokens": 5, "output_tokens": 2}, {"input_tokens": 3}) == {
        "input_tokens": 8,
        "output_tokens": 2,
    }


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
    r = RunNode(id=new_node_id(), parent_id=p.id, text="Invoice number 42.")
    p.children.append(r.id)
    root.children.append(p.id)
    doc.add_node(p)
    doc.add_node(r)
    return doc


class _UsageClient(LLMClient):
    async def complete(self, system, user, *, tools=None):  # pragma: no cover
        return LLMResponse(text="", tool_calls=[])

    async def converse(self, system, messages, *, tools=None):
        # Two turns: one tool call (search) then a final answer; each reports usage.
        if not any(m.get("role") == "tool" for m in messages):
            return LLMResponse(
                text="",
                tool_calls=[{"id": "c1", "name": "search", "input": {"query": "invoice"}}],
                usage={"input_tokens": 10, "output_tokens": 4},
            )
        return LLMResponse(
            text="It is 42.", tool_calls=[], usage={"input_tokens": 12, "output_tokens": 3}
        )


async def test_agent_loop_tallies_usage_across_turns():
    client = _UsageClient()
    run = await run_agent_loop(
        _doc(), "invoice number?", llm=client, orchestrator=SemanticOrchestratorImpl(client)
    )
    assert run.usage == {"input_tokens": 22, "output_tokens": 7}
