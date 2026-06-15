"""Reversible patches apply and revert exactly."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def _orchestrator():
    return SemanticOrchestratorImpl(LocalNoopClient())


def _first_run(doc):
    return next(n for n in doc.nodes.values() if n.type == "run")


def test_set_text_apply_then_revert_restores_original():
    doc = TxtAdapter().parse(b"original text")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="set_text", target_id=run.id, payload={"text": "new text"})],
        created_at=datetime.now(timezone.utc),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes[run.id].text == "new text"

    reverted = orch.revert(applied, patch)
    assert reverted.nodes[run.id].text == "original text"


def test_interpret_with_noop_client_returns_empty_patch():
    doc = TxtAdapter().parse(b"hello")
    orch = _orchestrator()
    patch = asyncio.run(orch.interpret(doc, "make it formal"))
    assert patch.patches == []
    assert patch.intent == "make it formal"
