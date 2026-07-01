"""Dry-run preview for a proposed patch.

Turns a list of patch ops into a human-readable before/after summary **without** mutating the
document, so the UI can show "here's exactly what will change" and the user approves before anything
is committed. Deterministic and offline — the same preview is produced whether the ops came from the
LLM planner or from explicit client ops.
"""

from __future__ import annotations

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.model.patch import Patch
from docos.services.semantic.retrieval import node_search_text

_MAX_SNIPPET = 160

# Human labels per op for the summary line.
_OP_LABEL = {
    "set_text": "text edit",
    "set_table_cell": "cell edit",
    "update_node": "format change",
    "retag": "retag",
    "redact": "redaction",
    "remove_node": "deletion",
    "sanitize_metadata": "metadata scrub",
}


class PatchChange(BaseModel):
    op: str
    target_id: str | None = None
    label: str
    before: str | None = None
    after: str | None = None


class PatchPreview(BaseModel):
    """A non-committed summary of what a patch would do."""

    change_count: int
    summary: str
    changes: list[PatchChange]


def _snippet(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:_MAX_SNIPPET] + "…" if len(text) > _MAX_SNIPPET else text


def _change_for(doc: CanonicalDocument, op: Patch) -> PatchChange:
    label = _OP_LABEL.get(op.op, op.op)
    node = doc.nodes.get(op.target_id) if op.target_id else None

    if op.op in ("set_text", "set_table_cell"):
        before = node_search_text(doc, node) if node is not None else ""
        return PatchChange(
            op=op.op,
            target_id=op.target_id,
            label=label,
            before=_snippet(before),
            after=_snippet(str(op.payload.get("text", ""))),
        )
    if op.op == "redact":
        before = node_search_text(doc, node) if node is not None else ""
        return PatchChange(
            op=op.op,
            target_id=op.target_id,
            label=label,
            before=_snippet(before),
            after="(removed from exports)",
        )
    if op.op == "remove_node":
        before = node_search_text(doc, node) if node is not None else ""
        return PatchChange(
            op=op.op,
            target_id=op.target_id,
            label=label,
            before=_snippet(before) or (node.type if node else ""),
            after="(deleted)",
        )
    if op.op == "update_node":
        changed = ", ".join(f"{k}={v}" for k, v in op.payload.items())
        return PatchChange(op=op.op, target_id=op.target_id, label=label, after=_snippet(changed))
    if op.op == "retag":
        before = ", ".join(node.tags) if node is not None else ""
        after = ", ".join(op.payload.get("tags", []))
        return PatchChange(
            op=op.op,
            target_id=op.target_id,
            label=label,
            before=_snippet(before),
            after=_snippet(after),
        )
    if op.op == "sanitize_metadata":
        return PatchChange(op=op.op, target_id=None, label=label, after="strip embedded metadata")
    return PatchChange(op=op.op, target_id=op.target_id, label=label)


def build_preview(doc: CanonicalDocument, ops: list[Patch]) -> PatchPreview:
    """Summarize the ops as before/after changes against ``doc`` (no mutation)."""
    changes = [_change_for(doc, op) for op in ops]
    counts: dict[str, int] = {}
    for c in changes:
        counts[c.label] = counts.get(c.label, 0) + 1
    if not changes:
        summary = "No changes — the instruction produced no edits."
    else:
        parts = [f"{n} {label}{'s' if n > 1 else ''}" for label, n in counts.items()]
        summary = f"{len(changes)} change{'s' if len(changes) > 1 else ''}: " + ", ".join(parts)
    return PatchPreview(change_count=len(changes), summary=summary, changes=changes)
