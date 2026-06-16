"""Accessibility auto-remediation — generate reversible patches that raise the a11y score.

The 2026 differentiator in remediation tools (Allyant, axesPDF) is automatic tagging.
Here it's expressed as ordinary reversible patch ops over the canonical model, so the
remediation is versioned and undoable like any other edit, and works across formats:
- tag heading nodes with their semantic level ("H1"…"H6"),
- assign reading order to top-level blocks,
- add alt-text placeholders to images that lack a description (flagged for human review).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.model.patch import Patch

_ALT_PLACEHOLDER = "(image — description needed)"


def remediation_ops(doc: CanonicalDocument) -> list[Patch]:
    """The minimal set of ops that improves accessibility without altering content."""
    ops: list[Patch] = []

    for node in doc.nodes.values():
        if node.type == "heading":
            tag = f"H{min(max(int(getattr(node, 'level', 1) or 1), 1), 6)}"
            if tag not in node.tags:
                ops.append(
                    Patch(op="retag", target_id=node.id, payload={"tags": [*node.tags, tag]})
                )

    for index, child in enumerate(doc.children_of(doc.root_id)):
        if child.reading_order is None:
            ops.append(
                Patch(op="update_node", target_id=child.id, payload={"reading_order": index})
            )

    for node in doc.nodes.values():
        if node.type == "image" and not getattr(node, "alt_text", None):
            ops.append(
                Patch(op="update_node", target_id=node.id, payload={"alt_text": _ALT_PLACEHOLDER})
            )

    return ops
