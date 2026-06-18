"""CSV adapter."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import RootNode, RunNode, TableCellNode, TableNode, TableRowNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_CSV_MIMES = ("text/csv", "application/csv")


class CsvAdapter(FormatAdapter):
    format_id = "csv"
    supported_mimes = _CSV_MIMES

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        text = data.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="csv",
                source_mime="text/csv",
                created_at=now,
                modified_at=now,
                page_count=1,
            ),
        )
        doc.add_node(root)
        table = TableNode(
            id=new_node_id("table"),
            parent_id=root.id,
            rows=len(rows),
            cols=max((len(r) for r in rows), default=0),
        )
        root.children.append(table.id)
        doc.add_node(table)
        for ri, row_values in enumerate(rows):
            row = TableRowNode(id=new_node_id("row"), parent_id=table.id, row=ri)
            for ci in range(table.cols):
                cell = TableCellNode(
                    id=new_node_id("cell"),
                    parent_id=row.id,
                    row=ri,
                    col=ci,
                    header=ri == 0,
                )
                run = RunNode(
                    id=new_node_id("run"),
                    parent_id=cell.id,
                    text=row_values[ci] if ci < len(row_values) else "",
                )
                cell.children.append(run.id)
                row.children.append(cell.id)
                doc.add_node(cell)
                doc.add_node(run)
            table.children.append(row.id)
            doc.add_node(row)
        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("CsvAdapter.render_preview - table renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        from docos.services.docengine.writers.markup import model_to_csv

        return model_to_csv(doc)
