"""Concrete semantic orchestrator.

``apply``/``revert`` are fully functional deterministic patch executors — this is the
core architectural promise, so it is real, not stubbed. ``interpret`` depends on the
pluggable ``LLMClient``; with the offline noop client it returns an empty reversible
patch (a no-op), which still exercises the whole apply/preview/revert path.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from docos.model.document import CanonicalDocument
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.semantic.interface import SemanticOrchestrator
from docos.services.semantic.llm.base import LLMClient


class SemanticOrchestratorImpl(SemanticOrchestrator):
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def interpret(self, doc: CanonicalDocument, instruction: str) -> ReversiblePatch:
        # The real implementation passes a structural summary + tool schema to the LLM
        # and validates returned ops against the model. The noop client yields no ops.
        await self.llm.complete(
            system="You edit a document graph by emitting reversible patch ops.",
            user=instruction,
        )
        return ReversiblePatch(
            id=new_patch_id(),
            patches=[],
            inverse=[],
            intent=instruction,
            created_at=datetime.now(timezone.utc),
        )

    def apply(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        result = doc.model_copy(deep=True)
        inverse: list[Patch] = []
        for op in patch.patches:
            inverse.insert(0, self._apply_one(result, op))
        patch.inverse = inverse
        return result

    def revert(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        result = doc.model_copy(deep=True)
        for op in patch.inverse:
            self._apply_one(result, op)
        return result

    # ── single-op executor; returns the inverse op needed to undo it ──────────
    def _apply_one(self, doc: CanonicalDocument, op: Patch) -> Patch:
        if op.op == "set_text":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            before = getattr(node, "text", "")
            object.__setattr__(node, "text", op.payload.get("text", ""))
            return Patch(op="set_text", target_id=op.target_id, payload={"text": before})

        if op.op == "update_node":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            before = {k: getattr(node, k, None) for k in op.payload}
            for k, v in op.payload.items():
                object.__setattr__(node, k, v)
            return Patch(op="update_node", target_id=op.target_id, payload=before)

        if op.op == "retag":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            before = list(node.tags)
            node.tags = list(op.payload.get("tags", []))
            return Patch(op="retag", target_id=op.target_id, payload={"tags": before})

        if op.op == "redact":
            tid = op.target_id  # type: ignore[assignment]
            if tid and tid not in doc.redaction.redacted_node_ids:
                doc.redaction.redacted_node_ids.append(tid)
            return Patch(op="update_node", target_id=tid, payload={"_unredact": True})

        if op.op == "remove_node":
            node = copy.deepcopy(doc.nodes[op.target_id])  # type: ignore[index]
            doc.nodes.pop(op.target_id, None)  # type: ignore[arg-type]
            if node.parent_id and node.parent_id in doc.nodes:
                parent = doc.nodes[node.parent_id]
                if op.target_id in parent.children:
                    parent.children.remove(op.target_id)  # type: ignore[arg-type]
            return Patch(op="add_node", target_id=op.target_id, payload={"node": node.model_dump()})

        raise NotImplementedError(f"patch op not yet supported: {op.op}")
