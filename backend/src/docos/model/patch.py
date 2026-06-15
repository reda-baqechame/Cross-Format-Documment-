"""Reversible patches — the unit of every edit.

The semantic layer never regenerates whole files. It produces a
:class:`ReversiblePatch`: a list of forward ``Patch`` ops plus the exact inverse
ops needed to undo them. This is what makes AI-assisted edits safe to preview,
apply, and revert with a complete audit trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PatchOp = Literal[
    "add_node",
    "remove_node",
    "update_node",
    "move_node",
    "set_text",
    "retag",
    "redact",
    "unredact",
    "sanitize_metadata",
    "restore_metadata",
]


class Patch(BaseModel):
    """A single forward operation against the node graph."""

    op: PatchOp
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReversiblePatch(BaseModel):
    id: str
    patches: list[Patch]  # forward changes
    inverse: list[Patch] = Field(default_factory=list)  # exact undo, computed at apply time
    intent: str | None = None  # natural-language instruction that produced it
    created_by: str = "system"
    created_at: datetime
