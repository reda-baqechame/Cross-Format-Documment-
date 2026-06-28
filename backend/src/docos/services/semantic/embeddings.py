"""Embedding seam for semantic search (Phase F4).

Default-off: with no embedding provider configured, retrieval stays deterministic BM25 (see
``search.semantic_retrieve``). When ``EMBEDDING_PROVIDER=openai`` is set, text is embedded and
ranked by cosine similarity so a query for "salary" can match a passage that only says
"compensation" — true semantic recall, not keyword overlap. The provider is vendor-agnostic behind
``EmbeddingProvider`` so a local model (e.g. bge via fastembed) can drop in later without changes.

Embeddings are cached per (model, text) in-process to avoid re-embedding the same nodes; no schema
change is required. Everything degrades safely: any provider error falls back to keyword retrieval.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from functools import lru_cache

from docos.settings import get_settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text (order preserved)."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings (text-embedding-3-small by default). Lazy import; needs an API key."""

    def __init__(self, api_key: str | None, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedding_provider() -> EmbeddingProvider | None:
    """The configured provider, or ``None`` when embeddings are off (the default)."""
    s = get_settings()
    if s.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            s.openai_api_key, s.embedding_model or "text-embedding-3-small"
        )
    return None


def embeddings_enabled() -> bool:
    return get_embedding_provider() is not None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@lru_cache(maxsize=8192)
def _embed_one_cached(model: str, text: str) -> tuple[float, ...]:
    provider = get_embedding_provider()
    if provider is None:  # pragma: no cover - guarded by callers
        return ()
    vecs = provider.embed([text])
    return tuple(vecs[0]) if vecs else ()


def rank_by_similarity(
    query: str, candidates: list[tuple[str, str]], k: int
) -> list[tuple[str, str]]:
    """Rank ``(id, text)`` candidates by embedding cosine similarity to ``query`` (top-k).

    Cached per text so repeated ranking over the same document is cheap. Returns ``[]`` when no
    provider is configured so callers can fall back to keyword retrieval.
    """
    provider = get_embedding_provider()
    if provider is None or not candidates:
        return []
    model = get_settings().embedding_model or "text-embedding-3-small"
    qvec = list(_embed_one_cached(model, query))
    if not qvec:
        return []
    scored: list[tuple[float, str, str]] = []
    for node_id, text in candidates:
        vec = list(_embed_one_cached(model, text))
        scored.append((cosine(qvec, vec), node_id, text))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [(node_id, text) for _, node_id, text in scored[:k]]
