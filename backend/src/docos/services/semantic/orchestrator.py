"""Concrete semantic orchestrator.

``apply``/``revert`` are fully functional deterministic patch executors — this is the
core architectural promise, so it is real, not stubbed. ``interpret`` depends on the
pluggable ``LLMClient``; with the offline noop client it returns an empty reversible
patch (a no-op), which still exercises the whole apply/preview/revert path.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from pydantic import TypeAdapter

from docos.model.document import CanonicalDocument
from docos.model.ids import new_node_id, new_patch_id
from docos.model.nodes import AnyNode, ImageNode, RunNode, TableCellNode, TableRowNode
from docos.model.patch import Patch, ReversiblePatch
from docos.services.provenance.health import RISKY_META_KEYS
from docos.services.semantic import prompt
from docos.services.semantic.interface import SemanticOrchestrator
from docos.services.semantic.llm.base import LLMClient

# Fields a client may set via ``update_node``. Restricting the keys keeps callers from
# injecting arbitrary attributes onto a node (e.g. shadowing ``type`` or ``children``).
_UPDATABLE_NODE_FIELDS = frozenset(
    {
        "text",
        "bold",
        "italic",
        "underline",
        "font",
        "size",
        "color",
        "link_href",
        "level",
        "style",
        "alignment",
        "alt_text",
        "ordered",
        "value",
        "header",
        "note",
        "resolved",
        "reading_order",
        "page_number",
        "width",
        "height",
        "rotation",
        "field_name",
        "field_kind",
        "required",
        "placeholder",
        "help_text",
        "options",
        "validation_pattern",
        "default_value",
    }
)


def _clamp_index(index: int | None, count: int) -> int:
    if index is None:
        return count
    return max(0, min(index, count))


def _insert_child(doc: CanonicalDocument, parent_id: str, child_id: str, index: int | None) -> None:
    parent = doc.nodes[parent_id]
    child = doc.nodes[child_id]
    if child_id in parent.children:
        parent.children.remove(child_id)
    parent.children.insert(_clamp_index(index, len(parent.children)), child_id)
    child.parent_id = parent_id


def _subtree_ids(doc: CanonicalDocument, root_id: str) -> list[str]:
    out: list[str] = []
    stack = [root_id]
    while stack:
        nid = stack.pop()
        node = doc.nodes.get(nid)
        if node is None:
            continue
        out.append(nid)
        stack.extend(reversed(node.children))
    return out


def _dump_subtree(doc: CanonicalDocument, root_id: str) -> list[dict]:
    return [copy.deepcopy(doc.nodes[nid]).model_dump() for nid in _subtree_ids(doc, root_id)]


def _restore_subtree(
    doc: CanonicalDocument,
    nodes_data: list[dict],
    *,
    parent_id: str | None,
    index: int | None,
) -> str:
    nodes = [TypeAdapter(AnyNode).validate_python(n) for n in nodes_data]
    if not nodes:
        raise ValueError("empty subtree")
    for node in nodes:
        doc.nodes[node.id] = node
    root = nodes[0]
    if parent_id:
        _insert_child(doc, parent_id, root.id, index)
    return root.id


def _remove_subtree(
    doc: CanonicalDocument, root_id: str
) -> tuple[list[dict], str | None, int | None]:
    node = doc.nodes[root_id]
    parent_id = node.parent_id
    index: int | None = None
    if parent_id and parent_id in doc.nodes:
        siblings = doc.nodes[parent_id].children
        if root_id in siblings:
            index = siblings.index(root_id)
            siblings.remove(root_id)
    data = _dump_subtree(doc, root_id)
    for nid in _subtree_ids(doc, root_id):
        doc.nodes.pop(nid, None)
        if nid in doc.redaction.redacted_node_ids:
            doc.redaction.redacted_node_ids.remove(nid)
    return data, parent_id, index


def _clone_subtree(doc: CanonicalDocument, root_id: str) -> tuple[str, list[AnyNode]]:
    ids = _subtree_ids(doc, root_id)
    mapping = {old: new_node_id(doc.nodes[old].type) for old in ids}
    clones: list[AnyNode] = []
    for old in ids:
        clone = copy.deepcopy(doc.nodes[old])
        object.__setattr__(clone, "id", mapping[old])
        clone.parent_id = mapping.get(clone.parent_id or "", clone.parent_id)
        clone.children = [mapping[cid] for cid in clone.children if cid in mapping]
        clones.append(clone)
    return mapping[root_id], clones


def _row_cells(doc: CanonicalDocument, row: AnyNode) -> list[AnyNode]:
    return [
        doc.nodes[cid]
        for cid in row.children
        if cid in doc.nodes and doc.nodes[cid].type == "table_cell"
    ]


def _table_rows(doc: CanonicalDocument, table: AnyNode) -> list[AnyNode]:
    return [
        doc.nodes[cid]
        for cid in table.children
        if cid in doc.nodes and doc.nodes[cid].type == "table_row"
    ]


def _renumber_table(doc: CanonicalDocument, table_id: str) -> None:
    table = doc.nodes.get(table_id)
    if table is None or table.type != "table":
        return
    rows = _table_rows(doc, table)
    max_cols = 0
    for ri, row in enumerate(rows):
        object.__setattr__(row, "row", ri)
        cells = _row_cells(doc, row)
        max_cols = max(max_cols, len(cells))
        for ci, cell in enumerate(cells):
            object.__setattr__(cell, "row", ri)
            object.__setattr__(cell, "col", ci)
    object.__setattr__(table, "rows", len(rows))
    object.__setattr__(table, "cols", max_cols)


def _cell_text(doc: CanonicalDocument, cell: AnyNode) -> str:
    return "".join(
        getattr(doc.nodes[cid], "text", "")
        for cid in cell.children
        if cid in doc.nodes and doc.nodes[cid].type == "run"
    )


def _first_run_child(doc: CanonicalDocument, node: AnyNode) -> RunNode | None:
    for cid in node.children:
        child = doc.nodes.get(cid)
        if child is not None and child.type == "run":
            return child  # type: ignore[return-value]
    return None


class SemanticOrchestratorImpl(SemanticOrchestrator):
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def interpret(self, doc: CanonicalDocument, instruction: str) -> ReversiblePatch:
        # Hand the model a digest of the editable nodes plus the emit_patch tool, then
        # validate the ops it returns against the live graph. The noop client returns no
        # tool calls, so this yields an empty (no-op) patch offline — fully deterministic.
        response = await self.llm.complete(
            system=prompt.SYSTEM_PROMPT,
            user=prompt.build_user_prompt(doc, instruction),
            tools=[prompt.EDIT_TOOL],
        )
        patches = prompt.ops_from_tool_calls(doc, response.tool_calls)
        return ReversiblePatch(
            id=new_patch_id(),
            patches=patches,
            inverse=[],
            intent=instruction,
            created_at=datetime.now(UTC),
        )

    def apply(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        result = doc.model_copy(deep=True)
        inverse: list[Patch] = []
        for op in patch.patches:
            inverse.insert(0, self._apply_one(result, op))
        patch.inverse = inverse
        return result

    def revert(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        result = doc.model_copy(deep=True)
        for op in patch.inverse:
            self._apply_one(result, op)
        return result

    # ── single-op executor; returns the inverse op needed to undo it ──────────
    def _apply_one(self, doc: CanonicalDocument, op: Patch) -> Patch:
        if op.op == "set_text":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            before = getattr(node, "text", "")
            object.__setattr__(node, "text", op.payload.get("text", ""))
            return Patch(op="set_text", target_id=op.target_id, payload={"text": before})

        if op.op == "update_node":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            fields = {k: v for k, v in op.payload.items() if k in _UPDATABLE_NODE_FIELDS}
            before = {k: getattr(node, k, None) for k in fields}
            for k, v in fields.items():
                object.__setattr__(node, k, v)
            return Patch(op="update_node", target_id=op.target_id, payload=before)

        if op.op == "retag":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            before = list(node.tags)
            node.tags = list(op.payload.get("tags", []))
            return Patch(op="retag", target_id=op.target_id, payload={"tags": before})

        if op.op == "redact":
            tid = op.target_id  # type: ignore[assignment]
            if tid and tid not in doc.redaction.redacted_node_ids:
                doc.redaction.redacted_node_ids.append(tid)
            return Patch(op="unredact", target_id=tid)

        if op.op == "unredact":
            tid = op.target_id
            if tid and tid in doc.redaction.redacted_node_ids:
                doc.redaction.redacted_node_ids.remove(tid)
            return Patch(op="redact", target_id=tid)

        if op.op == "sanitize_metadata":
            before = {k: doc.meta.custom[k] for k in RISKY_META_KEYS if doc.meta.custom.get(k)}
            was_sanitized = doc.redaction.metadata_sanitized
            for k in before:
                doc.meta.custom.pop(k, None)
            doc.redaction.metadata_sanitized = True
            return Patch(
                op="restore_metadata",
                payload={"custom": before, "was_sanitized": was_sanitized},
            )

        if op.op == "restore_metadata":
            restored = dict(op.payload.get("custom", {}))
            doc.meta.custom.update(restored)
            doc.redaction.metadata_sanitized = bool(op.payload.get("was_sanitized", False))
            return Patch(
                op="sanitize_metadata",
                payload={"_restored_keys": list(restored)},
            )

        if op.op == "remove_node":
            nid = op.target_id
            node = doc.nodes[nid]  # type: ignore[index]
            data, parent_id, index = _remove_subtree(doc, nid)  # type: ignore[arg-type]
            if parent_id and parent_id in doc.nodes and doc.nodes[parent_id].type == "table":
                _renumber_table(doc, parent_id)
            return Patch(
                op="add_node",
                target_id=nid,
                payload={
                    "node": node.model_dump(),
                    "nodes": data,
                    "parent_id": parent_id,
                    "index": index,
                },
            )

        if op.op == "add_node":
            nodes_payload = op.payload.get("nodes")
            if nodes_payload:
                node_id = _restore_subtree(
                    doc,
                    nodes_payload,
                    parent_id=op.payload.get("parent_id"),
                    index=op.payload.get("index"),
                )
                parent_id = op.payload.get("parent_id")
                if parent_id and parent_id in doc.nodes and doc.nodes[parent_id].type == "table":
                    _renumber_table(doc, parent_id)
                return Patch(op="remove_node", target_id=node_id)

            node = TypeAdapter(AnyNode).validate_python(op.payload["node"])
            doc.nodes[node.id] = node
            parent_id = op.payload.get("parent_id", node.parent_id)
            if parent_id and parent_id in doc.nodes:
                _insert_child(doc, parent_id, node.id, op.payload.get("index"))
                if doc.nodes[parent_id].type == "table":
                    _renumber_table(doc, parent_id)
            return Patch(op="remove_node", target_id=node.id)

        if op.op in ("duplicate_node", "duplicate_page"):
            source = doc.nodes[op.target_id]  # type: ignore[index]
            if op.op == "duplicate_page" and source.type != "page":
                raise ValueError("duplicate_page target must be a page")
            new_root_id, clones = _clone_subtree(doc, source.id)
            for clone in clones:
                doc.nodes[clone.id] = clone
            parent_id = op.payload.get("parent_id") or source.parent_id
            index = op.payload.get("index")
            if (
                index is None
                and parent_id
                and parent_id in doc.nodes
                and source.id in doc.nodes[parent_id].children
            ):
                index = doc.nodes[parent_id].children.index(source.id) + 1
            if parent_id and parent_id in doc.nodes:
                _insert_child(doc, parent_id, new_root_id, index)
            return Patch(op="remove_node", target_id=new_root_id)

        if op.op == "insert_table_row":
            table = doc.nodes[op.target_id]  # type: ignore[index]
            if table.type != "table":
                raise ValueError("insert_table_row target must be a table")
            rows = _table_rows(doc, table)
            index = _clamp_index(op.payload.get("index"), len(rows))
            row_payload = op.payload.get("row_nodes")
            if row_payload:
                row_id = _restore_subtree(doc, row_payload, parent_id=table.id, index=index)
            else:
                cols = int(op.payload.get("cols") or getattr(table, "cols", 0) or 1)
                values = list(op.payload.get("values", []))
                row = TableRowNode(id=new_node_id("row"), parent_id=table.id, row=index)
                doc.nodes[row.id] = row
                for col in range(cols):
                    cell = TableCellNode(
                        id=new_node_id("cell"), parent_id=row.id, row=index, col=col
                    )
                    run = RunNode(
                        id=new_node_id("run"),
                        parent_id=cell.id,
                        text=str(values[col]) if col < len(values) else "",
                    )
                    cell.children.append(run.id)
                    row.children.append(cell.id)
                    doc.nodes[cell.id] = cell
                    doc.nodes[run.id] = run
                _insert_child(doc, table.id, row.id, index)
                row_id = row.id
            _renumber_table(doc, table.id)
            return Patch(op="remove_node", target_id=row_id)

        if op.op == "delete_table_row":
            table = doc.nodes[op.target_id]  # type: ignore[index]
            if table.type != "table":
                raise ValueError("delete_table_row target must be a table")
            rows = _table_rows(doc, table)
            if not rows:
                raise ValueError("table has no rows")
            row_id = op.payload.get("row_id")
            row = (
                doc.nodes.get(row_id)
                if row_id
                else rows[_clamp_index(op.payload.get("index"), len(rows) - 1)]
            )
            if row is None or row.type != "table_row":
                raise ValueError("table row not found")
            index = rows.index(row)
            data, _parent_id, _old_index = _remove_subtree(doc, row.id)
            _renumber_table(doc, table.id)
            return Patch(
                op="insert_table_row",
                target_id=table.id,
                payload={"index": index, "row_nodes": data},
            )

        if op.op == "insert_table_col":
            table = doc.nodes[op.target_id]  # type: ignore[index]
            if table.type != "table":
                raise ValueError("insert_table_col target must be a table")
            rows = _table_rows(doc, table)
            current_cols = max((len(_row_cells(doc, row)) for row in rows), default=0)
            index = _clamp_index(op.payload.get("index"), current_cols)
            restored_cells = list(op.payload.get("cells", []))
            inserted_ids: list[str] = []
            values = list(op.payload.get("values", []))
            for row_i, row in enumerate(rows):
                if row_i < len(restored_cells):
                    cell_id = _restore_subtree(
                        doc, restored_cells[row_i], parent_id=row.id, index=index
                    )
                else:
                    cell = TableCellNode(
                        id=new_node_id("cell"), parent_id=row.id, row=row_i, col=index
                    )
                    run = RunNode(
                        id=new_node_id("run"),
                        parent_id=cell.id,
                        text=str(values[row_i]) if row_i < len(values) else "",
                    )
                    cell.children.append(run.id)
                    doc.nodes[cell.id] = cell
                    doc.nodes[run.id] = run
                    _insert_child(doc, row.id, cell.id, index)
                    cell_id = cell.id
                inserted_ids.append(cell_id)
            _renumber_table(doc, table.id)
            return Patch(
                op="delete_table_col",
                target_id=table.id,
                payload={"index": index, "cell_ids": inserted_ids},
            )

        if op.op == "delete_table_col":
            table = doc.nodes[op.target_id]  # type: ignore[index]
            if table.type != "table":
                raise ValueError("delete_table_col target must be a table")
            rows = _table_rows(doc, table)
            index = op.payload.get("index")
            cell_ids = list(op.payload.get("cell_ids", []))
            removed: list[list[dict]] = []
            if not cell_ids:
                max_cols = max((len(_row_cells(doc, row)) for row in rows), default=0)
                index = _clamp_index(index, max(max_cols - 1, 0))
            for row_i, row in enumerate(rows):
                cells = _row_cells(doc, row)
                cell_id = cell_ids[row_i] if row_i < len(cell_ids) else None
                cell = (
                    doc.nodes.get(cell_id)
                    if cell_id
                    else (cells[index] if index is not None and index < len(cells) else None)
                )
                if cell is None or cell.type != "table_cell":
                    continue
                data, _parent_id, _old_index = _remove_subtree(doc, cell.id)
                removed.append(data)
            _renumber_table(doc, table.id)
            return Patch(
                op="insert_table_col",
                target_id=table.id,
                payload={"index": index, "cells": removed},
            )

        if op.op == "set_table_cell":
            cell = doc.nodes[op.target_id]  # type: ignore[index]
            if cell.type != "table_cell":
                raise ValueError("set_table_cell target must be a table cell")
            before = {
                "text": _cell_text(doc, cell),
                "header": getattr(cell, "header", False),
                "attrs": copy.deepcopy(cell.attrs),
            }
            if "text" in op.payload:
                run = _first_run_child(doc, cell)
                if run is None:
                    run = RunNode(id=new_node_id("run"), parent_id=cell.id, text="")
                    doc.nodes[run.id] = run
                    cell.children.append(run.id)
                object.__setattr__(run, "text", str(op.payload.get("text") or ""))
            if "header" in op.payload:
                object.__setattr__(cell, "header", bool(op.payload["header"]))
            if "number_format" in op.payload:
                if op.payload["number_format"]:
                    cell.attrs["number_format"] = op.payload["number_format"]
                else:
                    cell.attrs.pop("number_format", None)
            if "formula" in op.payload:
                # A formula string ("=A1+B1") exports as a real Excel formula (recomputed on open);
                # an empty value clears it back to plain text.
                formula = op.payload["formula"]
                if isinstance(formula, str) and formula.strip():
                    cell.attrs["formula"] = formula.strip()
                else:
                    cell.attrs.pop("formula", None)
            return Patch(op="set_table_cell", target_id=cell.id, payload=before)

        if op.op == "insert_image":
            parent_id = op.target_id or op.payload.get("parent_id") or doc.root_id
            if parent_id not in doc.nodes:
                raise ValueError("insert_image parent not found")
            node = ImageNode(
                id=op.payload.get("id") or new_node_id("img"),
                parent_id=parent_id,
                blob_ref=op.payload["blob_ref"],
                mime=op.payload.get("mime", "image/png"),
                alt_text=op.payload.get("alt_text"),
                bbox=op.payload.get("bbox"),
                attrs=dict(op.payload.get("attrs", {})),
            )
            doc.nodes[node.id] = node
            _insert_child(doc, parent_id, node.id, op.payload.get("index"))
            return Patch(op="remove_node", target_id=node.id)

        if op.op in ("replace_image", "set_image_attrs"):
            image = doc.nodes[op.target_id]  # type: ignore[index]
            if image.type != "image":
                raise ValueError(f"{op.op} target must be an image")
            keys = ("blob_ref", "mime", "alt_text", "bbox", "attrs")
            before = {k: copy.deepcopy(getattr(image, k, None)) for k in keys if k in op.payload}
            for key in keys:
                if key in op.payload:
                    object.__setattr__(image, key, copy.deepcopy(op.payload[key]))
            return Patch(op=op.op, target_id=image.id, payload=before)

        if op.op == "insert_link":
            run = doc.nodes[op.target_id]  # type: ignore[index]
            if run.type != "run":
                raise ValueError("insert_link target must be a text run")
            before = {"link_href": getattr(run, "link_href", None)}
            object.__setattr__(
                run, "link_href", op.payload.get("href") or op.payload.get("link_href")
            )
            return Patch(op="insert_link", target_id=run.id, payload=before)

        if op.op == "set_list_attrs":
            node = doc.nodes[op.target_id]  # type: ignore[index]
            if node.type != "list":
                raise ValueError("set_list_attrs target must be a list")
            before = {"ordered": getattr(node, "ordered", False)}
            if "ordered" in op.payload:
                object.__setattr__(node, "ordered", bool(op.payload["ordered"]))
            return Patch(op="set_list_attrs", target_id=node.id, payload=before)

        if op.op == "set_page_attrs":
            page = doc.nodes[op.target_id]  # type: ignore[index]
            if page.type != "page":
                raise ValueError("set_page_attrs target must be a page")
            allowed = {"page_number", "width", "height", "rotation", "bbox", "attrs"}
            before = {k: copy.deepcopy(getattr(page, k, None)) for k in allowed if k in op.payload}
            for key in allowed:
                if key in op.payload:
                    object.__setattr__(page, key, copy.deepcopy(op.payload[key]))
            return Patch(op="set_page_attrs", target_id=page.id, payload=before)

        if op.op == "move_node":
            nid = op.target_id  # type: ignore[assignment]
            node = doc.nodes[nid]  # type: ignore[index]
            old_parent = node.parent_id
            old_index: int | None = None
            if old_parent and old_parent in doc.nodes:
                siblings = doc.nodes[old_parent].children
                if nid in siblings:
                    old_index = siblings.index(nid)  # type: ignore[arg-type]
                    siblings.remove(nid)  # type: ignore[arg-type]
            new_parent = op.payload.get("parent_id") or old_parent
            if new_parent and new_parent in doc.nodes:
                children = doc.nodes[new_parent].children
                index = op.payload.get("index")
                if index is None or index > len(children):
                    index = len(children)
                children.insert(index, nid)
                node.parent_id = new_parent
                if doc.nodes[new_parent].type == "table":
                    _renumber_table(doc, new_parent)
            if old_parent and old_parent in doc.nodes and doc.nodes[old_parent].type == "table":
                _renumber_table(doc, old_parent)
            return Patch(
                op="move_node", target_id=nid, payload={"parent_id": old_parent, "index": old_index}
            )

        raise NotImplementedError(f"patch op not yet supported: {op.op}")
