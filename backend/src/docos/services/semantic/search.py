"""Unified retrieval entry point — semantic when configured, deterministic keyword otherwise.

Callers (the agent's ``search`` tool, Q&A, notebook) should retrieve through ``semantic_retrieve``
so they automatically get embedding-based recall when ``EMBEDDING_PROVIDER`` is set, and fall back
to the always-available BM25 keyword ranking otherwise. Redaction-awareness and citation shape are
inherited from ``reader`` (redacted nodes are never candidates).
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic import embeddings, reader

_MAX_CITATIONS = 5


def semantic_retrieve(
    doc: CanonicalDocument, query: str, k: int = _MAX_CITATIONS
) -> list[tuple[str, str]]:
    """Top-k ``(node_id, text)`` for ``query``: embedding cosine when enabled, else BM25.

    Any embedding error or empty result falls back to keyword retrieval, so this never fails closed.
    """
    if embeddings.embeddings_enabled():
        candidates = reader._text_nodes(doc)
        try:
            ranked = embeddings.rank_by_similarity(query, candidates, k)
        except Exception:  # noqa: BLE001 - degrade to keyword retrieval, never fail the request
            ranked = []
        if ranked:
            return ranked
    return reader.retrieve(doc, query, k=k)
