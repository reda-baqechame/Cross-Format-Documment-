"""Canonical document node taxonomy.

The model is a typed, discriminated node graph stored as a flat registry
(``CanonicalDocument.nodes: dict[NodeId, AnyNode]``) plus parent/child edges. A
flat registry keyed by stable id is what lets reversible patches target any node
directly, regardless of how deep it sits in the tree.

Format-specific data that has no first-class field is preserved in ``attrs`` so it
is never silently dropped on round-trip — fidelity is a core product promise.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from docos.model.geometry import BBox

NodeType = Literal[
    "root",
    "page",
    "paragraph",
    "run",
    "heading",
    "list",
    "list_item",
    "table",
    "table_row",
    "table_cell",
    "image",
    "field",
    "comment",
    "annotation",
    "metadata_block",
]


class BaseNode(BaseModel):
    """Common shape for every node in the graph."""

    id: str
    type: NodeType
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)  # ordered child node ids
    bbox: BBox | None = None
    reading_order: int | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)  # preserved format-specific extras
    tags: list[str] = Field(default_factory=list)  # semantic / a11y tags, e.g. "H1", "PII"


class RootNode(BaseNode):
    type: Literal["root"] = "root"


class PageNode(BaseNode):
    type: Literal["page"] = "page"
    page_number: int
    width: float
    height: float
    rotation: int = 0


class ParagraphNode(BaseNode):
    type: Literal["paragraph"] = "paragraph"
    style: str | None = None
    alignment: str | None = None


class HeadingNode(BaseNode):
    type: Literal["heading"] = "heading"
    level: int = 1
    style: str | None = None
    alignment: str | None = None


class RunNode(BaseNode):
    """An inline text span carrying its own formatting."""

    type: Literal["run"] = "run"
    text: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font: str | None = None
    size: float | None = None
    color: str | None = None
    link_href: str | None = None


class ListNode(BaseNode):
    type: Literal["list"] = "list"
    ordered: bool = False


class ListItemNode(BaseNode):
    type: Literal["list_item"] = "list_item"


class TableNode(BaseNode):
    type: Literal["table"] = "table"
    rows: int = 0
    cols: int = 0


class TableRowNode(BaseNode):
    type: Literal["table_row"] = "table_row"
    row: int = 0


class TableCellNode(BaseNode):
    type: Literal["table_cell"] = "table_cell"
    row: int = 0
    col: int = 0
    row_span: int = 1
    col_span: int = 1
    header: bool = False


class ImageNode(BaseNode):
    type: Literal["image"] = "image"
    blob_ref: str  # BlobStore key — image bytes are never inlined in the model
    mime: str = "image/png"
    alt_text: str | None = None
    ocr_confidence: float | None = None


class FieldNode(BaseNode):
    """A form field / template placeholder."""

    type: Literal["field"] = "field"
    field_name: str
    field_kind: str = "text"  # text | checkbox | signature | date | ...
    value: str | None = None


class CommentNode(BaseNode):
    type: Literal["comment"] = "comment"
    author: str | None = None
    created_at: datetime | None = None
    resolved: bool = False
    text: str = ""


class AnnotationNode(BaseNode):
    type: Literal["annotation"] = "annotation"
    kind: str = "highlight"
    note: str | None = None


class MetadataBlockNode(BaseNode):
    type: Literal["metadata_block"] = "metadata_block"
    data: dict[str, Any] = Field(default_factory=dict)


# Discriminated union used everywhere a node value is (de)serialized.
AnyNode = Annotated[
    RootNode
    | PageNode
    | ParagraphNode
    | HeadingNode
    | RunNode
    | ListNode
    | ListItemNode
    | TableNode
    | TableRowNode
    | TableCellNode
    | ImageNode
    | FieldNode
    | CommentNode
    | AnnotationNode
    | MetadataBlockNode,
    Field(discriminator="type"),
]
