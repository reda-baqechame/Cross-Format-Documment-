"""The document root and its trust/policy state.

``CanonicalDocument`` is the object every service exchanges. It carries the node
graph plus the cross-format trust state (permissions, redaction, accessibility,
signature) that powers the document-health panel — the product's key differentiator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from docos.model.nodes import AnyNode

_NODE_ADAPTER: TypeAdapter[AnyNode] = TypeAdapter(AnyNode)


class Permissions(BaseModel):
    can_edit: bool = True
    can_export: bool = True
    can_copy: bool = True
    encrypted: bool = False
    password_protected: bool = False


class RedactionState(BaseModel):
    """Tracks redaction so the UI can warn that hiding != removing."""

    redacted_node_ids: list[str] = Field(default_factory=list)
    metadata_sanitized: bool = False
    pending: list[str] = Field(default_factory=list)


class AccessibilityState(BaseModel):
    has_doc_title: bool = False
    tagged: bool = False
    images_missing_alt: list[str] = Field(default_factory=list)
    reading_order_ok: bool = False
    score: float = 0.0  # 0..1, computed by the provenance/health service


class SignatureState(BaseModel):
    signed: bool = False
    signature_valid: bool | None = None
    ready_for_signing: bool = False


class DocumentMeta(BaseModel):
    title: str | None = None
    author: str | None = None
    source_format: str  # "txt" | "docx" | "pdf" | ...
    source_mime: str
    created_at: datetime
    modified_at: datetime
    page_count: int = 0
    # Raw embedded metadata, kept so it can be inspected & sanitized (trust control).
    custom: dict[str, Any] = Field(default_factory=dict)


class CanonicalDocument(BaseModel):
    schema_version: str = "1.0"
    doc_id: str
    root_id: str
    nodes: dict[str, AnyNode] = Field(default_factory=dict)
    meta: DocumentMeta
    permissions: Permissions = Field(default_factory=Permissions)
    redaction: RedactionState = Field(default_factory=RedactionState)
    accessibility: AccessibilityState = Field(default_factory=AccessibilityState)
    signature: SignatureState = Field(default_factory=SignatureState)
    content_hash: str | None = None  # canonical hash for versioning

    # ── graph helpers ────────────────────────────────────────────────────────
    def add_node(self, node: AnyNode) -> AnyNode:
        self.nodes[node.id] = node
        return node

    def get(self, node_id: str) -> AnyNode | None:
        return self.nodes.get(node_id)

    def children_of(self, node_id: str) -> list[AnyNode]:
        node = self.nodes.get(node_id)
        if node is None:
            return []
        return [self.nodes[cid] for cid in node.children if cid in self.nodes]

    def walk(self, start_id: str | None = None):
        """Depth-first traversal yielding nodes in reading order."""
        root = start_id or self.root_id
        stack = [root]
        while stack:
            nid = stack.pop()
            node = self.nodes.get(nid)
            if node is None:
                continue
            yield node
            stack.extend(reversed(node.children))
