"""Reversible patches apply and revert exactly."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

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
        created_at=datetime.now(UTC),
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


def test_update_node_apply_then_revert_restores_fields():
    doc = TxtAdapter().parse(b"plain run")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="update_node", target_id=run.id, payload={"bold": True, "italic": True})
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes[run.id].bold is True and applied.nodes[run.id].italic is True

    reverted = orch.revert(applied, patch)
    assert reverted.nodes[run.id].bold is False and reverted.nodes[run.id].italic is False


def test_update_node_ignores_unknown_payload_keys():
    doc = TxtAdapter().parse(b"text")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="update_node", target_id=run.id, payload={"type": "heading", "bold": True})
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    # 'type' is not an updatable field, so it must be left untouched.
    assert applied.nodes[run.id].type == "run"
    assert applied.nodes[run.id].bold is True


def test_redact_apply_adds_id_and_revert_removes_it():
    doc = TxtAdapter().parse(b"secret value")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="redact", target_id=run.id)],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert run.id in applied.redaction.redacted_node_ids

    reverted = orch.revert(applied, patch)
    assert run.id not in reverted.redaction.redacted_node_ids


def test_sanitize_metadata_op_clears_keys_and_revert_restores():
    doc = TxtAdapter().parse(b"body")
    doc.meta.custom = {"author": "Alice", "revision": "3", "keywords": "safe"}
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="sanitize_metadata")],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert "author" not in applied.meta.custom
    assert "revision" not in applied.meta.custom
    assert applied.meta.custom.get("keywords") == "safe"  # non-risky key kept
    assert applied.redaction.metadata_sanitized is True

    reverted = orch.revert(applied, patch)
    assert reverted.meta.custom.get("author") == "Alice"
    assert reverted.redaction.metadata_sanitized is False
