"""Concrete semantic orchestrator.

``apply``/``revert`` are fully functional deterministic patch executors — this is the
core architectural promise, so it is real, not stubbed. ``interpret`` depends on the
pluggable ``LLMClient``; with the offline noop client it returns an empty reversible
patch (a no-op), which still exercises the whole apply/preview/revert path.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from pydantic import TypeAdapter

from docos.model.document import CanonicalDocument
from docos.model.ids import new_patch_id
from docos.model.nodes import AnyNode
from docos.model.patch import Patch, ReversiblePatch
from docos.services.provenance.health import RISKY_META_KEYS
from docos.services.semantic import prompt
from docos.services.semantic.interface import SemanticOrchestrator
from docos.services.semantic.llm.base import LLMClient

# Fields a client may set via ``update_node``. Restricting the keys keeps callers from
# injecting arbitrary attributes onto a node (e.g. shadowing ``type`` or ``children``).
_UPDATABLE_NODE_FIELDS = frozenset(
    {
        "text",
        "bold",
        "italic",
        "underline",
        "font",
        "size",
        "color",
        "link_href",
        "level",
        "style",
        "alignment",
        "alt_text",
        "ordered",
        "value",
        "header",
        "note",
        "resolved",
    }
)


class SemanticOrchestratorImpl(SemanticOrchestrator):
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def interpret(self, doc: CanonicalDocument, instruction: str) -> ReversiblePatch:
        # Hand the model a digest of the editable nodes plus the emit_patch tool, then
        # validate the ops it returns against the live graph. The noop client returns no
        # tool calls, so this yields an empty (no-op) patch offline — fully deterministic.
        response = await self.llm.complete(
            system=prompt.SYSTEM_PROMPT,
            user=prompt.build_user_prompt(doc, instruction),
            tools=[prompt.EDIT_TOOL],
        )
        patches = prompt.ops_from_tool_calls(doc, response.tool_calls)
        return ReversiblePatch(
            id=new_patch_id(),
            patches=patches,
            inverse=[],
            intent=instruction,
            created_at=datetime.now(UTC),
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
            fields = {k: v for k, v in op.payload.items() if k in _UPDATABLE_NODE_FIELDS}
            before = {k: getattr(node, k, None) for k in fields}
            for k, v in fields.items():
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
            return Patch(op="unredact", target_id=tid)

        if op.op == "unredact":
            tid = op.target_id
            if tid and tid in doc.redaction.redacted_node_ids:
                doc.redaction.redacted_node_ids.remove(tid)
            return Patch(op="redact", target_id=tid)

        if op.op == "sanitize_metadata":
            before = {
                k: doc.meta.custom[k] for k in RISKY_META_KEYS if doc.meta.custom.get(k)
            }
            was_sanitized = doc.redaction.metadata_sanitized
            for k in before:
                doc.meta.custom.pop(k, None)
            doc.redaction.metadata_sanitized = True
            return Patch(
                op="restore_metadata",
                payload={"custom": before, "was_sanitized": was_sanitized},
            )

        if op.op == "restore_metadata":
            restored = dict(op.payload.get("custom", {}))
            doc.meta.custom.update(restored)
            doc.redaction.metadata_sanitized = bool(op.payload.get("was_sanitized", False))
            return Patch(
                op="sanitize_metadata",
                payload={"_restored_keys": list(restored)},
            )

        if op.op == "remove_node":
            nid = op.target_id
            node = copy.deepcopy(doc.nodes[nid])  # type: ignore[index]
            parent_id = node.parent_id
            index: int | None = None
            if parent_id and parent_id in doc.nodes:
                parent = doc.nodes[parent_id]
                if nid in parent.children:
                    index = parent.children.index(nid)  # type: ignore[arg-type]
                    parent.children.remove(nid)  # type: ignore[arg-type]
            doc.nodes.pop(nid, None)  # type: ignore[arg-type]
            return Patch(
                op="add_node",
                target_id=nid,
                payload={"node": node.model_dump(), "parent_id": parent_id, "index": index},
            )

        if op.op == "add_node":
            node = TypeAdapter(AnyNode).validate_python(op.payload["node"])
            doc.nodes[node.id] = node
            parent_id = op.payload.get("parent_id", node.parent_id)
            if parent_id and parent_id in doc.nodes:
                children = doc.nodes[parent_id].children
                if node.id not in children:
                    index = op.payload.get("index")
                    if index is None or index > len(children):
                        index = len(children)
                    children.insert(index, node.id)
                node.parent_id = parent_id
            return Patch(op="remove_node", target_id=node.id)

        if op.op == "move_node":
            nid = op.target_id  # type: ignore[assignment]
            node = doc.nodes[nid]  # type: ignore[index]
            old_parent = node.parent_id
            old_index: int | None = None
            if old_parent and old_parent in doc.nodes:
                siblings = doc.nodes[old_parent].children
                if nid in siblings:
                    old_index = siblings.index(nid)  # type: ignore[arg-type]
                    siblings.remove(nid)  # type: ignore[arg-type]
            new_parent = op.payload.get("parent_id") or old_parent
            if new_parent and new_parent in doc.nodes:
                children = doc.nodes[new_parent].children
                index = op.payload.get("index")
                if index is None or index > len(children):
                    index = len(children)
                children.insert(index, nid)
                node.parent_id = new_parent
            return Patch(
                op="move_node", target_id=nid, payload={"parent_id": old_parent, "index": old_index}
            )

        raise NotImplementedError(f"patch op not yet supported: {op.op}")
