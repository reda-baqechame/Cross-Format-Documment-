"""Markdown adapter.

Markdown is text, but it deserves its own source format so technical docs and AI
workflows do not get flattened into generic TXT on upload.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import HeadingNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_MD_MIMES = ("text/markdown", "text/x-markdown")


class MarkdownAdapter(FormatAdapter):
    format_id = "md"
    supported_mimes = _MD_MIMES

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        text = data.decode("utf-8", errors="replace")
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="md",
                source_mime="text/markdown",
                created_at=now,
                modified_at=now,
            ),
        )
        doc.add_node(root)
        for order, block in enumerate(b for b in text.split("\n\n") if b.strip()):
            stripped = block.strip()
            level = len(stripped) - len(stripped.lstrip("#"))
            if level and level <= 6 and stripped[level : level + 1] == " ":
                node = HeadingNode(
                    id=new_node_id("h"),
                    parent_id=root.id,
                    level=level,
                    reading_order=order,
                )
                run_text = stripped[level:].strip()
                node.tags.append(f"H{level}")
            else:
                node = ParagraphNode(id=new_node_id("p"), parent_id=root.id, reading_order=order)
                run_text = stripped
            run = RunNode(id=new_node_id("run"), parent_id=node.id, text=run_text)
            node.children.append(run.id)
            root.children.append(node.id)
            doc.add_node(node)
            doc.add_node(run)
        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("MarkdownAdapter.render_preview - text renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        from docos.services.docengine.writers.markup import model_to_markdown

        return model_to_markdown(doc)
