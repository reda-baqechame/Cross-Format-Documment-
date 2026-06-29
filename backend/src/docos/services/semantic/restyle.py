"""Global restyle — apply a formatting change across many runs at once.

"Any modification" includes bulk formatting: "make every heading bigger", "set the body font", "bold
every run that says TOTAL". Implemented once over the canonical model and compiled to the existing,
fully-reversible ``update_node`` op per matching run — so it inherits apply→commit→audit, undo, and
preview. Redaction-aware: redacted runs are skipped. Deterministic and offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.docengine.writers.redaction import is_redacted

# Only inline run-formatting fields may be set in bulk (the safe, reversible subset of update_node).
_STYLE_FIELDS = ("bold", "italic", "underline", "font", "size", "color")

Scope = Literal["all", "headings", "body", "matching"]


class RestyleStyle(BaseModel):
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font: str | None = None
    size: float | None = None
    color: str | None = None

    def payload(self) -> dict:
        return {f: getattr(self, f) for f in _STYLE_FIELDS if getattr(self, f) is not None}


def _ancestor_types(doc: CanonicalDocument, node_id: str) -> set[str]:
    types: set[str] = set()
    seen: set[str] = set()
    current: str | None = node_id
    while current and current not in seen:
        seen.add(current)
        node = doc.nodes.get(current)
        if node is None:
            break
        types.add(node.type)
        current = node.parent_id
    return types


def _in_scope(doc: CanonicalDocument, node, scope: Scope, find: str | None) -> bool:
    if scope == "all":
        return True
    if scope == "matching":
        return bool(find) and find in (getattr(node, "text", "") or "")
    ancestors = _ancestor_types(doc, node.id)
    if scope == "headings":
        return "heading" in ancestors
    if scope == "body":
        return "heading" not in ancestors
    return False


def build_restyle_patch(
    doc: CanonicalDocument,
    style: RestyleStyle,
    *,
    scope: Scope = "all",
    find: str | None = None,
) -> ReversiblePatch:
    """Build a reversible patch that applies ``style`` to every matching non-redacted run.

    Raises ``ValueError`` if no style fields are set or ``scope='matching'`` without ``find``.
    """
    payload = style.payload()
    if not payload:
        raise ValueError("at least one style field must be set")
    if scope == "matching" and not find:
        raise ValueError("scope='matching' requires a non-empty find string")

    patches: list[Patch] = []
    for node in doc.walk():
        if node.type != "run" or is_redacted(doc, node.id):
            continue
        if not _in_scope(doc, node, scope, find):
            continue
        # Only emit an op where something actually changes, so undo stays minimal.
        if any(getattr(node, field, None) != value for field, value in payload.items()):
            patches.append(Patch(op="update_node", target_id=node.id, payload=dict(payload)))

    return ReversiblePatch(
        id=new_patch_id(),
        patches=patches,
        intent=f"restyle scope={scope} {payload}",
        created_at=datetime.now(UTC),
    )
