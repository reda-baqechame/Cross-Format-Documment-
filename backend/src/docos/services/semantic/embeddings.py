"""Embedding seam for semantic search (Phase F4).

Default-off: with no embedding provider configured, retrieval stays deterministic BM25 (see
``search.semantic_retrieve``). When a provider is set, text is embedded and ranked by cosine
similarity so a query for "salary" can match a passage that only says "compensation" — true
semantic recall, not keyword overlap.

Two providers ship:

* ``openai`` — ``text-embedding-3-small`` by default; needs ``OPENAI_API_KEY`` (data leaves box).
* ``local`` — ``BAAI/bge-small-en-v1.5`` via **fastembed** (Apache-2.0; weights MIT). Runs
  **fully offline, no API key**. Optional install (``pip install fastembed``); lazy-imported.

The provider is vendor-agnostic behind ``EmbeddingProvider``, the instance is memoised (so the local
model loads once), and vectors are cached two layers deep: an in-process LRU over a persistent,
content-addressed on-disk cache (survives restarts / multi-process deploys). Everything degrades
safely: any provider error falls back to keyword retrieval.
"""

from __future__ import annotations

import array as _array
import hashlib
import math
import sqlite3
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from docos.settings import get_settings

_OPENAI_DEFAULT = "text-embedding-3-small"
_LOCAL_DEFAULT = "BAAI/bge-small-en-v1.5"


class EmbeddingProvider(ABC):
    #: The model name; also the namespace under which vectors are cached.
    model: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text (order preserved)."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings (text-embedding-3-small by default). Lazy import; needs an API key."""

    def __init__(self, api_key: str | None, model: str = _OPENAI_DEFAULT) -> None:
        self.api_key = api_key
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class LocalEmbeddingProvider(EmbeddingProvider):
    """Offline embeddings via fastembed (BAAI/bge-small-en-v1.5). No network, no API key.

    The fastembed model is loaded lazily and held on the instance, so memoising the provider (see
    ``get_embedding_provider``) means the weights load once per process, not per request.
    """

    def __init__(self, model: str = _LOCAL_DEFAULT) -> None:
        self.model = model
        self._engine = None

    def _ensure(self):  # pragma: no cover - exercised only with the extra installed
        if self._engine is None:
            from fastembed import TextEmbedding

            self._engine = TextEmbedding(model_name=self.model)
        return self._engine

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        engine = self._ensure()
        return [list(vec) for vec in engine.embed(texts)]


@lru_cache(maxsize=8)
def _provider(kind: str, model: str, api_key: str | None) -> EmbeddingProvider:
    if kind == "local":
        return LocalEmbeddingProvider(model)
    return OpenAIEmbeddingProvider(api_key, model)


def get_embedding_provider() -> EmbeddingProvider | None:
    """The configured provider (memoised), or ``None`` when embeddings are off (the default)."""
    s = get_settings()
    if s.embedding_provider == "openai":
        return _provider("openai", s.embedding_model or _OPENAI_DEFAULT, s.openai_api_key)
    if s.embedding_provider == "local":
        return _provider("local", s.embedding_model or _LOCAL_DEFAULT, None)
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


# ── Persistent embedding cache ───────────────────────────────────────────────────────────────────
# Vectors are content-addressed by (model, sha256(text)). The on-disk SQLite layer survives restarts
# and is shared across processes; a small in-process dict sits on top to avoid the round-trip. Both
# layers degrade to "no cache" silently if the dir is unset or unwritable — caching is never load-
# bearing for correctness.
_MEM: dict[tuple[str, str], tuple[float, ...]] = {}
_MEM_LOCK = threading.Lock()
_MEM_MAX = 8192

_DISK_LOCK = threading.Lock()
_disk_conn: sqlite3.Connection | None = None
_disk_dir: str | None = None


def _key(model: str, text: str) -> str:
    return f"{model}\x00{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _disk() -> sqlite3.Connection | None:
    """The SQLite cache connection for the configured dir, re-opening if the dir changes."""
    global _disk_conn, _disk_dir
    cache_dir = get_settings().embedding_cache_dir or ""
    if cache_dir == _disk_dir:
        return _disk_conn
    with _DISK_LOCK:
        if _disk_conn is not None:
            try:
                _disk_conn.close()
            except Exception:  # noqa: BLE001
                pass
        _disk_conn = None
        _disk_dir = cache_dir
        if not cache_dir:
            return None
        try:
            p = Path(cache_dir)
            p.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(p / "embeddings.db"), check_same_thread=False)
            conn.execute("CREATE TABLE IF NOT EXISTS emb (k TEXT PRIMARY KEY, v BLOB NOT NULL)")
            conn.commit()
            _disk_conn = conn
        except Exception:  # noqa: BLE001 - any FS/db error: run without the disk layer
            _disk_conn = None
    return _disk_conn


def _disk_get(model: str, text: str) -> tuple[float, ...] | None:
    conn = _disk()
    if conn is None:
        return None
    try:
        with _DISK_LOCK:
            row = conn.execute("SELECT v FROM emb WHERE k=?", (_key(model, text),)).fetchone()
    except Exception:  # noqa: BLE001
        return None
    if not row:
        return None
    arr = _array.array("f")
    arr.frombytes(row[0])
    return tuple(arr)


def _disk_put(model: str, text: str, vec: tuple[float, ...]) -> None:
    conn = _disk()
    if conn is None:
        return
    try:
        blob = _array.array("f", vec).tobytes()
        with _DISK_LOCK:
            conn.execute(
                "INSERT OR REPLACE INTO emb (k, v) VALUES (?, ?)", (_key(model, text), blob)
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


def clear_cache() -> None:
    """Drop both cache layers and the memoised provider — for tests / explicit cache busting."""
    global _disk_conn, _disk_dir
    with _MEM_LOCK:
        _MEM.clear()
    with _DISK_LOCK:
        if _disk_conn is not None:
            try:
                _disk_conn.close()
            except Exception:  # noqa: BLE001
                pass
        _disk_conn = None
        _disk_dir = None
    _provider.cache_clear()


def _embed_one(provider: EmbeddingProvider, text: str) -> tuple[float, ...]:
    """Embed a single text, served from the in-process → disk → provider cache hierarchy."""
    model = provider.model
    mem_key = (model, text)
    with _MEM_LOCK:
        cached = _MEM.get(mem_key)
    if cached is not None:
        return cached

    vec = _disk_get(model, text)
    if vec is None:
        vecs = provider.embed([text])
        vec = tuple(vecs[0]) if vecs else ()
        if vec:
            _disk_put(model, text, vec)

    if vec:
        with _MEM_LOCK:
            if len(_MEM) >= _MEM_MAX:
                _MEM.clear()
            _MEM[mem_key] = vec
    return vec


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
    qvec = list(_embed_one(provider, query))
    if not qvec:
        return []
    scored: list[tuple[float, str, str]] = []
    for node_id, text in candidates:
        vec = list(_embed_one(provider, text))
        scored.append((cosine(qvec, vec), node_id, text))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [(node_id, text) for _, node_id, text in scored[:k]]
