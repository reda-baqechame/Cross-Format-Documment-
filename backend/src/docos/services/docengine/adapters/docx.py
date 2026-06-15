"""DOCX adapter (python-docx) — the second functional adapter.

Extracts paragraphs (with heading detection), inline runs with basic formatting,
tables, and core metadata. Embedded metadata is preserved in ``meta.custom`` so the
provenance layer can flag and sanitize it.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from docx import Document as DocxDocument

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

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocxAdapter(FormatAdapter):
    format_id = "docx"
    supported_mimes = (_DOCX_MIME,)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        src = DocxDocument(io.BytesIO(data))
        now = datetime.now(timezone.utc)
        root = RootNode(id=new_node_id("root"))

        core = src.core_properties
        meta = DocumentMeta(
            title=core.title or None,
            author=core.author or None,
            source_format="docx",
            source_mime=_DOCX_MIME,
            created_at=now,
            modified_at=now,
            page_count=1,
            custom={
                "category": core.category,
                "comments": core.comments,
                "keywords": core.keywords,
                "last_modified_by": core.last_modified_by,
                "revision": core.revision,
                "subject": core.subject,
            },
        )

        doc = CanonicalDocument(doc_id=new_doc_id(), root_id=root.id, meta=meta)
        doc.add_node(root)

        order = 0
        for para in src.paragraphs:
            style = (para.style.name if para.style else "") or ""
            node: ParagraphNode | HeadingNode
            if style.startswith("Heading"):
                level = _heading_level(style)
                node = HeadingNode(id=new_node_id(), parent_id=root.id, level=level, style=style)
                node.tags.append(f"H{level}")
            else:
                node = ParagraphNode(
                    id=new_node_id(),
                    parent_id=root.id,
                    style=style or None,
                    alignment=_alignment(para),
                )
            node.reading_order = order
            order += 1

            for run in para.runs:
                if not run.text:
                    continue
                rnode = RunNode(
                    id=new_node_id(),
                    parent_id=node.id,
                    text=run.text,
                    bold=bool(run.bold),
                    italic=bool(run.italic),
                    underline=bool(run.underline),
                    font=run.font.name,
                    size=float(run.font.size.pt) if run.font.size else None,
                )
                node.children.append(rnode.id)
                doc.add_node(rnode)

            root.children.append(node.id)
            doc.add_node(node)

        for table in src.tables:
            order = self._parse_table(doc, root, table, order)

        if meta.title:
            doc.accessibility.has_doc_title = True
        return doc

    def _parse_table(self, doc: CanonicalDocument, root, table, order: int) -> int:
        tnode = TableNode(
            id=new_node_id(),
            parent_id=root.id,
            rows=len(table.rows),
            cols=len(table.columns),
            reading_order=order,
        )
        for r, row in enumerate(table.rows):
            rownode = TableRowNode(id=new_node_id(), parent_id=tnode.id, row=r)
            for c, cell in enumerate(row.cells):
                cellnode = TableCellNode(id=new_node_id(), parent_id=rownode.id, row=r, col=c)
                run = RunNode(id=new_node_id(), parent_id=cellnode.id, text=cell.text)
                cellnode.children.append(run.id)
                rownode.children.append(cellnode.id)
                doc.add_node(cellnode)
                doc.add_node(run)
            tnode.children.append(rownode.id)
            doc.add_node(rownode)
        root.children.append(tnode.id)
        doc.add_node(tnode)
        return order + 1

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("DocxAdapter.render_preview — pending LibreOffice/render service")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("DocxAdapter.export — pending DOCX writer")


def _heading_level(style: str) -> int:
    try:
        return int(style.replace("Heading", "").strip() or "1")
    except ValueError:
        return 1


def _alignment(para) -> str | None:
    return str(para.alignment) if para.alignment is not None else None
