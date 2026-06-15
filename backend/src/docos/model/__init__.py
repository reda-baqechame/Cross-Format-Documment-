"""Canonical document model — the single source of truth.

Adapters parse files *into* a :class:`~docos.model.document.CanonicalDocument`; the
frontend renders *from* it; exporters serialize *from* it. Edits are applied as
reversible patches (:mod:`docos.model.patch`), never whole-file regeneration.
"""

from docos.model.document import (
    AccessibilityState,
    CanonicalDocument,
    DocumentMeta,
    Permissions,
    RedactionState,
    SignatureState,
)
from docos.model.geometry import BBox, Point
from docos.model.nodes import (
    AnyNode,
    BaseNode,
    CommentNode,
    FieldNode,
    HeadingNode,
    ImageNode,
    NodeType,
    PageNode,
    ParagraphNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.model.patch import Patch, PatchOp, ReversiblePatch

__all__ = [
    "AccessibilityState",
    "AnyNode",
    "BBox",
    "BaseNode",
    "CanonicalDocument",
    "CommentNode",
    "DocumentMeta",
    "FieldNode",
    "HeadingNode",
    "ImageNode",
    "NodeType",
    "PageNode",
    "ParagraphNode",
    "Patch",
    "PatchOp",
    "Permissions",
    "Point",
    "RedactionState",
    "ReversiblePatch",
    "RunNode",
    "SignatureState",
    "TableCellNode",
    "TableNode",
    "TableRowNode",
]
