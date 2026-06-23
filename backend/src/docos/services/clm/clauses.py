"""Clause library — insert a saved clause as a reversible patch.

Inserting a clause is an ordinary ``add_node`` mutation (a heading for the title plus a paragraph
per body line), so it's versioned, audited, and undoable like every other edit.
"""

from __future__ import annotations

from docos.model.ids import new_node_id
from docos.model.patch import Patch


def _block_op(parent_id: str, text: str, *, heading: bool) -> Patch:
    block_id = new_node_id("h" if heading else "p")
    run_id = new_node_id("run")
    block = {
        "id": block_id,
        "type": "heading" if heading else "paragraph",
        "parent_id": parent_id,
        "children": [run_id],
        "tags": ["H2"] if heading else [],
        "level": 2 if heading else None,
    }
    run = {"id": run_id, "type": "run", "parent_id": block_id, "children": [], "text": text}
    return Patch(
        op="add_node",
        payload={"node": block, "nodes": [block, run], "parent_id": parent_id, "index": None},
    )


def build_clause_insert_patches(parent_id: str, title: str, body: str) -> list[Patch]:
    """Add a clause (title heading + one paragraph per non-empty body line) under ``parent_id``."""
    ops: list[Patch] = []
    if title.strip():
        ops.append(_block_op(parent_id, title.strip(), heading=True))
    for line in body.splitlines():
        line = line.strip()
        if line:
            ops.append(_block_op(parent_id, line, heading=False))
    if not ops and body.strip():  # single-line body with no title
        ops.append(_block_op(parent_id, body.strip(), heading=False))
    return ops
