"""Email adapter (.eml / RFC-822) — open an email as a canonical document.

Headers (From/To/Cc/Subject/Date) become a metadata block + a heading; the body (plain text, or HTML
flattened to text) becomes paragraphs; attachment filenames are listed. Pure stdlib (``email``), no
new dependency, fully offline. Like every adapter it maps into the same node graph, so an email
converts to PDF/DOCX/etc. through the existing writers.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email import message_from_bytes
from email.policy import default as default_policy

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import HeadingNode, MetadataBlockNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_TAG = re.compile(r"<[^>]+>")
_HEADERS = ("From", "To", "Cc", "Date", "Subject")


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    return _TAG.sub("", text)


class EmlAdapter(FormatAdapter):
    format_id = "eml"
    supported_mimes = ("message/rfc822", "application/eml", "text/eml")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        msg = message_from_bytes(data, policy=default_policy)
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="eml",
                source_mime="message/rfc822",
                created_at=now,
                modified_at=now,
                title=str(msg.get("Subject", "") or "Email"),
                page_count=1,
            ),
        )
        doc.add_node(root)
        order = 0

        def _block(node, text: str) -> None:
            nonlocal order
            run = RunNode(id=new_node_id(), parent_id=node.id, text=text)
            node.children.append(run.id)
            node.reading_order = order
            order += 1
            root.children.append(node.id)
            doc.add_node(node)
            doc.add_node(run)

        # Subject as the document heading.
        subject = str(msg.get("Subject", "") or "(no subject)")
        _block(HeadingNode(id=new_node_id(), parent_id=root.id, level=1), subject)

        # Headers as a structured metadata block (provenance can inspect/sanitize) + visible recap.
        headers = {h: str(msg.get(h, "") or "") for h in _HEADERS if msg.get(h)}
        meta_node = MetadataBlockNode(
            id=new_node_id(), parent_id=root.id, reading_order=order, data=headers
        )
        order += 1
        root.children.append(meta_node.id)
        doc.add_node(meta_node)
        for key, value in headers.items():
            if key != "Subject":
                _block(ParagraphNode(id=new_node_id(), parent_id=root.id), f"{key}: {value}")

        # Body: prefer plain text; flatten HTML otherwise.
        body = ""
        try:
            part = msg.get_body(preferencelist=("plain", "html"))
            if part is not None:
                content = part.get_content()
                body = content if part.get_content_subtype() == "plain" else _html_to_text(content)
        except Exception:  # noqa: BLE001 - malformed MIME: degrade to the raw payload
            body = msg.get_payload(decode=False) if isinstance(msg.get_payload(), str) else ""

        for block in re.split(r"\n\s*\n", (body or "").strip()):
            block = block.strip()
            if block:
                _block(ParagraphNode(id=new_node_id(), parent_id=root.id), block)

        # Attachments: list filenames (content is not inlined into the model).
        names = [att.get_filename() for att in msg.iter_attachments() if att.get_filename()]
        if names:
            _block(
                ParagraphNode(id=new_node_id(), parent_id=root.id),
                "Attachments: " + ", ".join(names),
            )

        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("EmlAdapter.render_preview — email renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError(
            "EmlAdapter does not re-emit .eml; convert to another format via the writers"
        )
