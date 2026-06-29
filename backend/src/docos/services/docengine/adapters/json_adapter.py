"""JSON adapter — open a JSON document as a canonical document.

A top-level array of flat objects becomes a table (union of keys → columns); anything else is
flattened to ``dotted.path: value`` paragraphs so the structure is readable and convertible. Pure
stdlib, offline.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import (
    HeadingNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


def _flatten(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            out += _flatten(value, f"{prefix}{key}.")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            out += _flatten(value, f"{prefix}{i}.")
    else:
        out.append((prefix.rstrip(".") or "value", "" if obj is None else str(obj)))
    return out


class JsonAdapter(FormatAdapter):
    format_id = "json"
    supported_mimes = ("application/json", "text/json")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            obj = {"_raw": data.decode("utf-8", errors="replace")}

        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="json",
                source_mime="application/json",
                created_at=now,
                modified_at=now,
                title="JSON document",
                page_count=1,
            ),
        )
        doc.add_node(root)
        order = 0

        def _heading(text: str) -> None:
            nonlocal order
            h = HeadingNode(id=new_node_id(), parent_id=root.id, level=1, reading_order=order)
            run = RunNode(id=new_node_id(), parent_id=h.id, text=text)
            h.children.append(run.id)
            order += 1
            root.children.append(h.id)
            doc.add_node(h)
            doc.add_node(run)

        _heading("JSON document")

        # Array of flat objects → a single table.
        if (
            isinstance(obj, list)
            and obj
            and all(isinstance(x, dict) for x in obj)
            and all(all(not isinstance(v, (dict, list)) for v in x.values()) for x in obj)
        ):
            headers: list[str] = []
            for row in obj:
                for key in row:
                    if key not in headers:
                        headers.append(key)
            grid = [headers] + [
                ["" if row.get(h) is None else str(row.get(h, "")) for h in headers] for row in obj
            ]
            self._table(doc, root, grid, order)
            return doc

        # Otherwise flatten to path: value paragraphs.
        for path, value in _flatten(obj):
            para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=order)
            run = RunNode(id=new_node_id(), parent_id=para.id, text=f"{path}: {value}")
            para.children.append(run.id)
            order += 1
            root.children.append(para.id)
            doc.add_node(para)
            doc.add_node(run)
        return doc

    @staticmethod
    def _table(doc: CanonicalDocument, root: RootNode, grid: list[list[str]], order: int) -> None:
        cols = max((len(r) for r in grid), default=0)
        table = TableNode(
            id=new_node_id(), parent_id=root.id, reading_order=order, rows=len(grid), cols=cols
        )
        for r, cells in enumerate(grid):
            row = TableRowNode(id=new_node_id(), parent_id=table.id, row=r)
            for c in range(cols):
                cell = TableCellNode(
                    id=new_node_id(), parent_id=row.id, row=r, col=c, header=(r == 0)
                )
                run = RunNode(
                    id=new_node_id(),
                    parent_id=cell.id,
                    text=cells[c] if c < len(cells) else "",
                    bold=(r == 0),
                )
                cell.children.append(run.id)
                row.children.append(cell.id)
                doc.add_node(cell)
                doc.add_node(run)
            table.children.append(row.id)
            doc.add_node(row)
        root.children.append(table.id)
        doc.add_node(table)

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("JsonAdapter.render_preview — renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("JsonAdapter does not re-emit JSON; convert via the writers")
