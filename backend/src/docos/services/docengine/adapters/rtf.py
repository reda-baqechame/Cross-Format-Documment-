"""RTF adapter (striprtf).

Strips RTF control words to plain text, then builds the same paragraph/run structure
as the TXT adapter (one paragraph per non-empty line). Formatting beyond text isn't
recovered, but the content flows through the canonical model and exports cleanly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from striprtf.striprtf import rtf_to_text

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


class RtfAdapter(FormatAdapter):
    format_id = "rtf"
    supported_mimes = ("application/rtf", "text/rtf")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        text = rtf_to_text(data.decode("utf-8", errors="replace"))
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="rtf",
                source_mime="application/rtf",
                created_at=now,
                modified_at=now,
                page_count=1,
            ),
        )
        doc.add_node(root)

        order = 0
        for line in text.split("\n"):
            block = line.strip()
            if not block:
                continue
            para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=order)
            run = RunNode(id=new_node_id(), parent_id=para.id, text=block)
            para.children.append(run.id)
            root.children.append(para.id)
            doc.add_node(para)
            doc.add_node(run)
            order += 1

        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("RtfAdapter.render_preview — text renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("RtfAdapter.export — download as DOCX/TXT from the model")
