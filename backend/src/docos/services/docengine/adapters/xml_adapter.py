"""XML adapter — open a generic XML document as a canonical document.

Each element becomes an indented ``tag(attrs): text`` paragraph in document order, so arbitrary XML
is readable and convertible. Parsing is hardened against entity-expansion attacks: it prefers
``defusedxml`` when installed and otherwise uses a stdlib parser with entity declarations refused.
Offline, no required new dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import HeadingNode, ParagraphNode, RootNode, RunNode
from docos.services.docengine.interface import FormatAdapter
from docos.storage.blob import BlobStore


def _forbid_entities(*_args, **_kwargs):
    # Any <!ENTITY ...> declaration aborts the parse — kills billion-laughs / XXE before expansion.
    raise ValueError("XML entity declarations are not allowed")


def _safe_parse(data: bytes):
    """Parse XML with entity declarations / external DTDs refused (billion-laughs / XXE safe)."""
    try:  # defusedxml is the belt-and-suspenders path when present.
        from defusedxml.ElementTree import fromstring  # type: ignore

        return fromstring(data, forbid_dtd=True)
    except ModuleNotFoundError:
        import xml.etree.ElementTree as ET

        parser = ET.XMLParser()
        # expat refuses to declare any entity, so &lol2; etc. can never expand.
        parser.parser.EntityDeclHandler = _forbid_entities
        parser.parser.ExternalEntityRefHandler = lambda *_: False
        return ET.fromstring(data, parser=parser)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else str(tag)


class XmlAdapter(FormatAdapter):
    format_id = "xml"
    supported_mimes = ("application/xml", "text/xml")

    def parse(self, data: bytes, *, blob: BlobStore | None = None) -> CanonicalDocument:
        now = datetime.now(UTC)
        root_node = RootNode(id=new_node_id("root"))
        doc = CanonicalDocument(
            doc_id=new_doc_id(),
            root_id=root_node.id,
            meta=DocumentMeta(
                source_format="xml",
                source_mime="application/xml",
                created_at=now,
                modified_at=now,
                title="XML document",
                page_count=1,
            ),
        )
        doc.add_node(root_node)
        self._order = 0

        try:
            elem = _safe_parse(data)
        except Exception:  # noqa: BLE001 - unparsable: keep the raw text so nothing is lost
            self._para(doc, root_node, data.decode("utf-8", errors="replace"))
            return doc

        h = HeadingNode(
            id=new_node_id(), parent_id=root_node.id, level=1, reading_order=self._order
        )
        hrun = RunNode(id=new_node_id(), parent_id=h.id, text=f"<{_local(elem.tag)}>")
        h.children.append(hrun.id)
        self._order += 1
        root_node.children.append(h.id)
        doc.add_node(h)
        doc.add_node(hrun)

        self._walk(doc, root_node, elem, depth=0)
        return doc

    def _walk(self, doc: CanonicalDocument, root: RootNode, elem, *, depth: int) -> None:
        indent = "  " * depth
        attrs = " ".join(f'{_local(k)}="{v}"' for k, v in elem.attrib.items())
        label = _local(elem.tag) + (f" [{attrs}]" if attrs else "")
        text = (elem.text or "").strip()
        self._para(doc, root, f"{indent}{label}" + (f": {text}" if text else ""))
        for child in list(elem):
            self._walk(doc, root, child, depth=depth + 1)

    def _para(self, doc: CanonicalDocument, root: RootNode, text: str) -> None:
        para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=self._order)
        run = RunNode(id=new_node_id(), parent_id=para.id, text=text)
        para.children.append(run.id)
        self._order += 1
        root.children.append(para.id)
        doc.add_node(para)
        doc.add_node(run)

    def render_preview(self, doc: CanonicalDocument, page: int) -> bytes:
        raise NotImplementedError("XmlAdapter.render_preview — renders in the canvas")

    def export(self, doc: CanonicalDocument, *, target_mime: str) -> bytes:
        raise NotImplementedError("XmlAdapter does not re-emit XML; convert via the writers")
