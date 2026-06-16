"""Deterministic retrieval + extraction for document Q&A and summaries."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic import reader


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    doc = CanonicalDocument(
        doc_id="d1",
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
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        doc.add_node(para)
        doc.add_node(run)
    return doc


def test_retrieve_ranks_by_term_overlap():
    doc = _doc(
        [
            "The annual report covers revenue and growth.",
            "Our refund policy allows returns within 30 days.",
            "Contact the support team for help.",
        ]
    )
    hits = reader.retrieve(doc, "What is the refund policy?")
    assert hits[0][0] == "r1"  # the refund-policy node ranks first


def test_retrieve_ignores_stopwords_only_query():
    doc = _doc(["Some content here."])
    assert reader.retrieve(doc, "the is of and") == []


def test_extractive_summary_uses_leading_sentences():
    doc = _doc(["First sentence. Second sentence.", "Another paragraph entirely."])
    summary, lead = reader._extractive_summary(doc)
    assert "First sentence." in summary
    assert "Second sentence." not in summary  # only the lead sentence per node
    assert [nid for nid, _ in lead] == ["r0", "r1"]


def test_extractive_summary_empty_document():
    doc = _doc([])
    summary, lead = reader._extractive_summary(doc)
    assert lead == []
    assert "no extractable text" in summary


def test_redacted_nodes_excluded_from_retrieval():
    doc = _doc(["secret refund details here"])
    doc.redaction.redacted_node_ids.append("r0")
    assert reader.retrieve(doc, "refund") == []
