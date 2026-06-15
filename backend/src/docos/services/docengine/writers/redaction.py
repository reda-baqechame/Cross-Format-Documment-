"""Redaction enforcement shared by every writer.

The product promise is that redaction *removes* content, not merely hides it. Every
export path runs run text through :func:`run_text`, so redacted text never reaches
the exported bytes — a node is redacted if it (or any ancestor) is marked redacted.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode


def is_redacted(doc: CanonicalDocument, node_id: str | None) -> bool:
    """True if ``node_id`` or any of its ancestors is in the redaction set."""
    redacted = doc.redaction.redacted_node_ids
    if not redacted:
        return False
    seen: set[str] = set()
    current = node_id
    while current and current not in seen:
        if current in redacted:
            return True
        seen.add(current)
        node = doc.nodes.get(current)
        current = node.parent_id if node else None
    return False


def run_text(doc: CanonicalDocument, node: AnyNode) -> str:
    """The exportable text of a run — empty when redacted (true removal)."""
    if is_redacted(doc, node.id):
        return ""
    return getattr(node, "text", "")
