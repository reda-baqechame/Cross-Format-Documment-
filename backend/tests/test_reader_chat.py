"""Unit coverage for the conversational reader.chat path: history-biased + redaction-aware."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic import reader
from docos.services.semantic.llm.noop import LocalNoopClient


def _doc(*lines: str) -> tuple[CanonicalDocument, list[str]]:
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
    run_ids: list[str] = []
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
        run_ids.append(r.id)
    return doc, run_ids


def test_history_query_includes_recent_user_turns():
    history = [
        reader.ChatTurn(role="user", content="Tell me about the headquarters."),
        reader.ChatTurn(role="assistant", content="Sure."),
    ]
    q = reader._history_query(history, "Where is it?")
    assert "headquarters" in q and "Where is it?" in q
    # Assistant turns are not folded into the retrieval query (only user intent biases recall).
    assert "Sure." not in q


def test_chat_offline_is_deterministic_and_cited():
    doc, _ = _doc("Our headquarters are in Berlin.", "Refunds within 30 days.")
    res = asyncio.run(
        reader.chat(doc, [], "How long for a refund?", LocalNoopClient(), use_llm=False)
    )
    assert res.used_llm is False
    assert "30 days" in res.answer
    assert res.citations


def test_chat_never_returns_redacted_text():
    doc, run_ids = _doc("Public mission statement.", "Secret salary is $250,000.")
    doc.redaction.redacted_node_ids.append(run_ids[1])  # redact the salary line
    res = asyncio.run(reader.chat(doc, [], "What is the salary?", LocalNoopClient(), use_llm=False))
    assert "250,000" not in res.answer
    assert all("250,000" not in c.excerpt for c in res.citations)
