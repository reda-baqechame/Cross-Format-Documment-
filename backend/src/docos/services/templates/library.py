"""Template instantiation — turn a saved model snapshot into a fresh document.

A template is just a stored :class:`CanonicalDocument` snapshot. Stamping out a new
document from it must produce a *fully independent* document: a new ``doc_id`` and a
fresh set of node ids, so edits, comments, and version history of the new document never
collide with the template (or with other documents minted from the same template).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from docos.model.document import CanonicalDocument
from docos.model.ids import new_doc_id, new_node_id
from docos.model.serialize import from_dict, to_dict


def snapshot(doc: CanonicalDocument) -> dict[str, Any]:
    """Serialize a document into a reusable template payload (its content + structure)."""
    data = to_dict(doc)
    # A template is structure, not a signed/owned artifact — drop instance-only trust state.
    data.pop("content_hash", None)
    data["signature"] = {}
    return data


def instantiate(model: dict[str, Any], *, title: str | None = None) -> CanonicalDocument:
    """Build a new, independent document from a stored template snapshot.

    Every node id (and the root id) is regenerated so the resulting document shares no
    identifiers with the template. Parent/child edges are rewritten through the same map,
    preserving the exact structure.
    """
    doc = from_dict(model)

    id_map: dict[str, str] = {old: new_node_id() for old in doc.nodes}
    remapped: dict[str, Any] = {}
    for old_id, node in doc.nodes.items():
        node.id = id_map[old_id]
        node.parent_id = id_map.get(node.parent_id) if node.parent_id else None
        node.children = [id_map[c] for c in node.children if c in id_map]
        remapped[node.id] = node

    doc.nodes = remapped
    doc.root_id = id_map.get(doc.root_id, doc.root_id)
    doc.doc_id = new_doc_id()

    now = datetime.now(UTC)
    doc.meta.created_at = now
    doc.meta.modified_at = now
    if title is not None:
        doc.meta.title = title

    # A freshly stamped document is unsigned and carries no prior content hash.
    doc.signature = doc.signature.__class__()
    doc.content_hash = None
    return doc
