"""HTML adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import HeadingNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore

_BLOCK_TAGS = {"p", "li", "td", "th", "blockquote", "section", "article", "div"}
_HTML_MIMES = ("text/html", "application/xhtml+xml")


class _TextBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, str]] = []
        self._tag_stack: list[str] = []
        self._current: list[str] = []
        self._current_tag = "p"

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _BLOCK_TAGS or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush()
            self._current_tag = tag
        self._tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush()
        if tag in self._tag_stack:
            self._tag_stack.remove(tag)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._current.append(data.strip())

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        text = " ".join(part for part in self._current if part).strip()
        if text:
            self.blocks.append((self._current_tag, text))
        self._current = []
        self._current_tag = "p"


class HtmlAdapter(FormatAdapter):
    format_id = "html"
    supported_mimes = _HTML_MIMES

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        parser = _TextBlocks()
        parser.feed(data.decode("utf-8", errors="replace"))
        parser.close()
        now = datetime.now(UTC)
        root = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root.id,
            meta=DocumentMeta(
                source_format="html",
                source_mime="text/html",
                created_at=now,
                modified_at=now,
            ),
        )
        doc.add_node(root)
        for order, (tag, text) in enumerate(parser.blocks):
            if tag.startswith("h") and tag[1:].isdigit():
                level = max(1, min(6, int(tag[1:])))
                node = HeadingNode(
                    id=new_node_id("h"), parent_id=root.id, level=level, reading_order=order
                )
                node.tags.append(f"H{level}")
            else:
                node = ParagraphNode(id=new_node_id("p"), parent_id=root.id, reading_order=order)
            run = RunNode(id=new_node_id("run"), parent_id=node.id, text=text)
            node.children.append(run.id)
            root.children.append(node.id)
            doc.add_node(node)
            doc.add_node(run)
        return doc

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("HtmlAdapter.render_preview - text renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        from docos.services.docengine.writers.markup import model_to_html

        return model_to_html(doc)
