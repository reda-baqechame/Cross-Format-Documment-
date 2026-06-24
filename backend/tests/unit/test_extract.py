"""Structured-data extraction over the canonical model."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic import extract


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    d = CanonicalDocument(
        doc_id="d",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    d.add_node(root)
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        d.add_node(para)
        d.add_node(run)
    return d


def test_extracts_entities():
    doc = _doc(["Invoice dated 2026-03-01 for $1,250.00, contact a@b.com or 90% complete."])
    types = {e.type for e in extract.extract(doc).entities}
    assert {"date", "money", "email", "percent"} <= types


def test_extracts_label_value_fields():
    doc = _doc(["Invoice Number: INV-2026-044", "Total Due: $99.00"])
    fields = {f.key: f.value for f in extract.extract(doc).fields}
    assert fields["Invoice Number"] == "INV-2026-044"
    assert fields["Total Due"] == "$99.00"


def test_entities_carry_provenance_and_dedupe():
    doc = _doc(["mail a@b.com", "again a@b.com"])
    emails = [e for e in extract.extract(doc).entities if e.type == "email"]
    assert len(emails) == 1  # deduped by (type, value)
    assert emails[0].node_id == "r0"


def test_redacted_nodes_excluded():
    doc = _doc(["secret a@b.com"])
    doc.redaction.redacted_node_ids.append("r0")
    assert extract.extract(doc).entities == []
