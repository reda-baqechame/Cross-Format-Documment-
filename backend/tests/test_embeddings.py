"""Embedding seam internals: persistent cache, hybrid fusion, and the offline local provider."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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


class _CountingProvider(embeddings.EmbeddingProvider):
    """Deterministic toy vectors; counts how many texts it actually embedded (cache misses)."""

    model = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        # 1-D vector from a stable hash so the same text always maps to the same point.
        return [[float(sum(ord(c) for c in t) % 97)] for t in texts]


def test_default_off_is_pure_bm25(monkeypatch):
    # With no provider, semantic_retrieve must be byte-identical to reader.retrieve (no regression).
    monkeypatch.setattr(embeddings, "embeddings_enabled", lambda: False)
    doc = _doc("Refund policy is 30 days.", "Shipping is free over $50.", "Returns accepted.")
    from docos.services.semantic import reader

    assert search.semantic_retrieve(doc, "refund returns", k=3) == reader.retrieve(
        doc, "refund returns", k=3
    )


def test_disk_cache_persists_and_dedupes(tmp_path, monkeypatch):
    # Point the persistent cache at a tmp dir; embedding the same text twice should hit the disk
    # layer the second time (provider not called again), and survive clearing the in-process layer.
    monkeypatch.setattr(
        embeddings, "get_settings", lambda: type("S", (), {"embedding_cache_dir": str(tmp_path)})()
    )
    embeddings.clear_cache()
    provider = _CountingProvider()

    v1 = embeddings._embed_one(provider, "hello world")
    assert provider.calls == 1
    # In-process hit: no new embed call.
    embeddings._embed_one(provider, "hello world")
    assert provider.calls == 1

    # Drop only the in-process layer; the on-disk vector must still serve the next lookup.
    with embeddings._MEM_LOCK:
        embeddings._MEM.clear()
    v2 = embeddings._embed_one(provider, "hello world")
    assert provider.calls == 1  # served from disk, provider untouched
    assert v1 == v2
    embeddings.clear_cache()


def test_rrf_fuses_keyword_and_dense(monkeypatch):
    # RRF must keep an exact keyword hit even when a dense list ranks a synonym first.
    vocab = {"compensation": [1.0, 0.0], "salary": [0.97, 0.05], "lunch": [0.0, 1.0]}

    def _vec(text: str):
        for word, v in vocab.items():
            if word in text.lower():
                return v
        return [0.0, 0.0]

    class FakeProvider(embeddings.EmbeddingProvider):
        model = "fake2"

        def embed(self, texts):
            return [_vec(t) for t in texts]

    monkeypatch.setattr(embeddings, "get_embedding_provider", lambda: FakeProvider())
    monkeypatch.setattr(embeddings, "embeddings_enabled", lambda: True)
    monkeypatch.setattr(embeddings, "_disk", lambda: None)
    embeddings.clear_cache()

    doc = _doc(
        "Your salary is set annually.", "Total compensation includes bonus.", "We had lunch."
    )
    hits = search.semantic_retrieve(doc, "salary", k=2)
    ids_text = " | ".join(t.lower() for _, t in hits)
    # Both the literal keyword ("salary") and the semantic match ("compensation") survive fusion.
    assert "salary" in ids_text and "compensation" in ids_text
    embeddings.clear_cache()


def test_local_provider_smoke():
    # Real offline model — only runs where the optional `fastembed` extra is installed; CI's default
    # install skips this cleanly.
    pytest.importorskip("fastembed")
    provider = embeddings.LocalEmbeddingProvider()
    vecs = provider.embed(["hello world"])
    assert vecs and len(vecs[0]) > 0
