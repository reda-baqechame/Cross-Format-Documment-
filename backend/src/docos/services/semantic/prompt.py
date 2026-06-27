"""Prompt construction + tool-call parsing for AI-assisted editing.

The orchestrator hands the LLM a compact digest of the editable nodes plus an
``emit_patch`` tool. The model replies with concrete ops, which we validate against
the live node graph before turning them into a :class:`ReversiblePatch` — the model
proposes, the deterministic engine disposes. Keeping this logic out of the client
makes it provider-agnostic and unit-testable without any network call.
"""

from __future__ import annotations

from typing import Any

from docos.model.document import CanonicalDocument
from docos.model.patch import Patch
from docos.services.semantic import retrieval

# Ops the model is allowed to emit. A safe, reversible subset of the full op set; broad structural
# surgery (add/move arbitrary nodes) stays out of the AI path. ``set_table_cell`` is included so the
# model can fix spreadsheet/table cells (pairs with the inline sheet editor).
_ALLOWED_OPS = {
    "set_text",
    "update_node",
    "retag",
    "redact",
    "remove_node",
    "sanitize_metadata",
    "set_table_cell",
}
_FORMAT_FIELDS = ("bold", "italic", "underline", "font", "size", "color")
# Cap the digest so a huge document can't blow the prompt budget.
_MAX_DIGEST_NODES = 400

SYSTEM_PROMPT = (
    "You edit a structured document by emitting reversible patch ops against its node "
    "graph. You are given a digest of the document's editable nodes (each with a stable "
    "id) and a user instruction. Translate the instruction into the minimal set of ops "
    "that satisfies it, then call the emit_patch tool exactly once with those ops.\n\n"
    "Ops:\n"
    "- set_text: replace a run's text (target_id = run id, text = new text).\n"
    "- update_node: change formatting on a run (target_id + any of bold/italic/underline).\n"
    "- retag: replace a node's semantic tags (target_id + tags).\n"
    "- redact: mark a node's text for true removal from exports (target_id).\n"
    "- remove_node: delete a node from the document (target_id).\n"
    "- set_table_cell: set a table/spreadsheet cell's text (target_id = cell id, text = value).\n"
    "- sanitize_metadata: strip risky embedded metadata (no target_id).\n\n"
    "Only target ids that appear in the digest. If the instruction cannot be satisfied "
    "with these ops, call emit_patch with an empty ops list."
)

EDIT_TOOL: dict[str, Any] = {
    "name": "emit_patch",
    "description": "Emit the ordered list of edit operations to apply to the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ops": {
                "type": "array",
                "description": "Edit operations, applied in order.",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": sorted(_ALLOWED_OPS)},
                        "target_id": {"type": "string"},
                        "text": {"type": "string"},
                        "bold": {"type": "boolean"},
                        "italic": {"type": "boolean"},
                        "underline": {"type": "boolean"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["op"],
                },
            }
        },
        "required": ["ops"],
    },
}


def build_user_prompt(doc: CanonicalDocument, instruction: str) -> str:
    """Instruction plus a compact, id-anchored digest of the *relevant* editable nodes.

    For large documents the digest is narrowed to the BM25-relevant nodes for the instruction
    (``retrieval.select_digest_nodes``) so the model sees the right context instead of just the
    first N nodes; small documents are shown whole.
    """
    selected = retrieval.select_digest_nodes(doc, instruction, limit=_MAX_DIGEST_NODES)
    lines: list[str] = []
    for node_id in selected:
        node = doc.nodes.get(node_id)
        if node is None:
            continue
        if node.type == "heading":
            lines.append(f"{node.id} [heading h{getattr(node, 'level', 1)}]")
            continue
        text = (retrieval.node_search_text(doc, node) or "").replace("\n", " ")
        if len(text) > 200:
            text = text[:200] + "…"
        label = "cell" if node.type == "table_cell" else "run"
        lines.append(f'{node.id} [{label}] "{text}"')
    digest = "\n".join(lines) if lines else "(no editable nodes)"
    return f"Instruction: {instruction}\n\nDocument nodes:\n{digest}"


def ops_from_tool_calls(doc: CanonicalDocument, tool_calls: list[dict]) -> list[Patch]:
    """Validate the model's emit_patch output into concrete, safe patch ops."""
    patches: list[Patch] = []
    for call in tool_calls:
        if call.get("name") != "emit_patch":
            continue
        for raw in (call.get("input") or {}).get("ops", []):
            patch = _coerce_op(doc, raw)
            if patch is not None:
                patches.append(patch)
    return patches


def _coerce_op(doc: CanonicalDocument, raw: dict) -> Patch | None:
    op = raw.get("op")
    if op not in _ALLOWED_OPS:
        return None
    target_id = raw.get("target_id")

    if op == "sanitize_metadata":
        return Patch(op="sanitize_metadata")

    # Every other allowed op needs a real target.
    if not target_id or target_id not in doc.nodes:
        return None

    if op == "set_text":
        return Patch(op="set_text", target_id=target_id, payload={"text": raw.get("text", "")})
    if op == "set_table_cell":
        node = doc.nodes.get(target_id)
        if node is None or node.type != "table_cell":
            return None
        return Patch(
            op="set_table_cell", target_id=target_id, payload={"text": raw.get("text", "")}
        )
    if op == "update_node":
        payload = {f: raw[f] for f in _FORMAT_FIELDS if f in raw}
        if not payload:
            return None
        return Patch(op="update_node", target_id=target_id, payload=payload)
    if op == "retag":
        return Patch(op="retag", target_id=target_id, payload={"tags": list(raw.get("tags", []))})
    if op == "redact":
        return Patch(op="redact", target_id=target_id)
    if op == "remove_node":
        return Patch(op="remove_node", target_id=target_id)
    return None
