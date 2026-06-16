"""Plain-text adapter — the simplest functional adapter.

Each blank-line-separated block becomes a paragraph with a single text run. This
keeps the canonical model honest: even TXT flows through the same node graph as
every richer format.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


class TxtAdapter(FormatAdapter):
    format_id = "txt"
    supported_mimes = ("text/plain",)

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        text = data.decode("utf-8", errors="replace")
        now = datetime.now(UTC)
        doc_id = new_doc_id()
        root = RootNode(id=new_node_id("root"))

        doc = CanonicalDocument(
            doc_id=doc_id,
            root_id=root.id,
            meta=DocumentMeta(
                source_format="txt",
                source_mime="text/plain",
                created_at=now,
                modified_at=now,
                page_count=1,
            ),
        )
        doc.add_node(root)

        order = 0
        blocks = [b for b in text.split("\n\n")]
        for block in blocks:
            para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=order)
            run = RunNode(id=new_node_id(), parent_id=para.id, text=block.strip("\n"))
            para.children.append(run.id)
            root.children.append(para.id)
            doc.add_node(para)
            doc.add_node(run)
            order += 1

        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("TxtAdapter.render_preview — text renders directly in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        if target_mime != "text/plain":
            raise NotImplementedError(f"TxtAdapter cannot export to {target_mime}")
        from docos.services.docengine.writers.redaction import run_text

        parts: list[str] = []
        for node in doc.walk():
            if node.type == "run":
                parts.append(run_text(doc, node))
        return "\n\n".join(parts).encode("utf-8")
