"""Semantic-search seam (Phase F4): BM25 fallback by default + embedding ranking when enabled."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.semantic import embeddings, search


def _doc(*lines: str) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def test_default_off_falls_back_to_keyword():
    # No provider configured → semantic_retrieve must equal the deterministic BM25 path.
    assert embeddings.embeddings_enabled() is False
    doc = _doc("The refund policy is 30 days.", "Shipping is free over $50.")
    hits = search.semantic_retrieve(doc, "refund", k=2)
    assert hits and any("refund" in t.lower() for _, t in hits)


def test_cosine_basic():
    assert embeddings.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert embeddings.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_embedding_ranking_beats_keyword_on_synonymy(monkeypatch):
    # A toy provider that maps salary/compensation near each other proves the seam ranks by meaning,
    # not keyword overlap — the thing BM25 can't do.
    vocab = {
        "compensation": [1.0, 0.0, 0.0],
        "salary": [0.96, 0.10, 0.0],
        "weather": [0.0, 0.0, 1.0],
    }

    def _vec(text: str) -> list[float]:
        for word, v in vocab.items():
            if word in text.lower():
                return v
        return [0.0, 0.0, 0.0]

    class FakeProvider(embeddings.EmbeddingProvider):
        model = "fake"

        def embed(self, texts):
            return [_vec(t) for t in texts]

    monkeypatch.setattr(embeddings, "get_embedding_provider", lambda: FakeProvider())
    monkeypatch.setattr(embeddings, "embeddings_enabled", lambda: True)
    monkeypatch.setattr(embeddings, "_disk", lambda: None)  # keep the cache off the repo tree
    embeddings.clear_cache()

    # A pure-synonym query ("salary") shares no keyword with the doc ("compensation"); only the
    # embedding leg of the fusion can surface it — which is exactly the BM25 gap we're closing.
    doc = _doc("Annual compensation is $150,000.", "The weather is nice today.")
    hits = search.semantic_retrieve(doc, "salary", k=1)
    assert hits and "compensation" in hits[0][1].lower()
    embeddings.clear_cache()
