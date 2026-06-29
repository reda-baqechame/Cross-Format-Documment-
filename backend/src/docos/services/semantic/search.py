"""Unified retrieval entry point — semantic when configured, deterministic keyword otherwise.

Callers (the agent's ``search`` tool, Q&A, notebook) should retrieve through ``semantic_retrieve``
so they automatically get embedding-based recall when an embedding provider is set, and the
always-available BM25 keyword ranking otherwise. Redaction-awareness and citation shape are
inherited from ``reader`` (redacted nodes are never candidates).

When embeddings are enabled we **fuse** dense and keyword rankings with Reciprocal Rank Fusion (RRF)
rather than replacing one with the other: semantic recall is added on top, but an exact keyword hit
can never be pushed out by the dense model. With embeddings off, behaviour is identical to plain
BM25 — a pure, no-regression fallback.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic import embeddings, reader

_MAX_CITATIONS = 5
# RRF damping constant (standard value): larger → flatter contribution from rank position.
_RRF_C = 60


def _rrf(rankings: list[list[tuple[str, str]]], k: int) -> list[tuple[str, str]]:
    """Reciprocal Rank Fusion of several ranked ``(node_id, text)`` lists → top-k fused list."""
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}
    for ranked in rankings:
        for rank, (node_id, text) in enumerate(ranked):
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (_RRF_C + rank + 1)
            texts.setdefault(node_id, text)
    ordered = sorted(scores, key=lambda nid: scores[nid], reverse=True)
    return [(nid, texts[nid]) for nid in ordered[:k]]


def semantic_retrieve(
    doc: CanonicalDocument, query: str, k: int = _MAX_CITATIONS
) -> list[tuple[str, str]]:
    """Top-k ``(node_id, text)`` for ``query``: BM25 fused with embedding cosine when enabled.

    Any embedding error or empty dense result falls back to keyword retrieval, so this never fails
    closed; with no provider configured it is exactly ``reader.retrieve`` (BM25).
    """
    keyword = reader.retrieve(doc, query, k=k)
    if not embeddings.embeddings_enabled():
        return keyword

    candidates = reader._text_nodes(doc)
    try:
        dense = embeddings.rank_by_similarity(query, candidates, k)
    except Exception:  # noqa: BLE001 - degrade to keyword retrieval, never fail the request
        dense = []
    if not dense:
        return keyword
    return _rrf([keyword, dense], k)
