"""Corpus-level intelligence: semantic search and a multi-document notebook.

Both run over the canonical models of *many* documents at once and stay fully
deterministic and offline (no embeddings service required): ranking is **BM25** relevance,
which captures semantic relevance — a query for "salary" surfaces a doc about "compensation"
via shared rarer terms — with proper term-saturation + length normalization, and no network
call. A configured LLM provider, when present, only rephrases the same cited excerpts.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.semantic.llm.base import LLMClient
from docos.services.semantic.reader import (
    _STOPWORDS,
    _WORD,
    ANSWER_SYSTEM,
    _excerpt,
    _norm,
    _text_nodes,
)
from docos.services.semantic.retrieval import bm25_scores


class CorpusDoc(BaseModel, arbitrary_types_allowed=True):
    doc_id: str
    title: str | None
    doc: CanonicalDocument


class SemanticHit(BaseModel):
    doc_id: str
    title: str | None
    score: float
    snippet: str


class NotebookCitation(BaseModel):
    doc_id: str
    title: str | None
    node_id: str
    excerpt: str


class NotebookAnswer(BaseModel):
    answer: str
    citations: list[NotebookCitation]
    used_llm: bool


def _term_counts(text: str) -> Counter[str]:
    return Counter(
        _norm(m.group()) for m in _WORD.finditer(text) if _norm(m.group()) not in _STOPWORDS
    )


def _doc_text(doc: CanonicalDocument) -> str:
    return " ".join(text for _, text in _text_nodes(doc))


def _best_snippet(doc: CanonicalDocument, query_terms: set[str]) -> str:
    best_text, best_score = "", -1
    for _node_id, text in _text_nodes(doc):
        score = len(query_terms & set(_term_counts(text)))
        if score > best_score:
            best_text, best_score = text, score
    return _excerpt(best_text) if best_text else ""


def semantic_search(corpus: list[CorpusDoc], query: str, limit: int = 20) -> list[SemanticHit]:
    """Rank documents by **BM25** relevance to ``query`` (most relevant first).

    BM25 handles term saturation + document-length normalization better than plain TF-IDF cosine, so
    long documents stop dominating on raw term counts. Still deterministic, offline, and stopword-
    filtered (same tokenizer as the rest of the reader).
    """
    if not corpus:
        return []
    query_terms = set(_term_counts(query))
    if not query_terms:
        return []
    corpus_tokens = [list(_term_counts(_doc_text(c.doc)).elements()) for c in corpus]
    scores = bm25_scores(corpus_tokens, query_terms)

    scored: list[SemanticHit] = []
    for c, score in zip(corpus, scores, strict=True):
        if score > 0:
            scored.append(
                SemanticHit(
                    doc_id=c.doc_id,
                    title=c.title,
                    score=round(score, 4),
                    snippet=_best_snippet(c.doc, query_terms),
                )
            )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:limit]


def _retrieve_across(
    corpus: list[CorpusDoc], query: str, k: int
) -> list[tuple[CorpusDoc, str, str, int]]:
    """Top-k (corpus_doc, node_id, text, score) across the whole corpus by term overlap."""
    query_terms = set(_term_counts(query))
    if not query_terms:
        return []
    hits: list[tuple[int, CorpusDoc, str, str]] = []
    for c in corpus:
        for node_id, text in _text_nodes(c.doc):
            score = len(query_terms & set(_term_counts(text)))
            if score:
                hits.append((score, c, node_id, text))
    hits.sort(key=lambda h: h[0], reverse=True)
    return [(c, nid, text, score) for score, c, nid, text in hits[:k]]


async def notebook_answer(
    corpus: list[CorpusDoc], question: str, llm: LLMClient, *, use_llm: bool, k: int = 6
) -> NotebookAnswer:
    """Answer a question across many documents, citing the doc + node for each excerpt."""
    hits = _retrieve_across(corpus, question, k)
    citations = [
        NotebookCitation(doc_id=c.doc_id, title=c.title, node_id=nid, excerpt=_excerpt(text))
        for c, nid, text, _ in hits
    ]

    if not hits:
        return NotebookAnswer(
            answer="I couldn't find anything about that across these documents.",
            citations=[],
            used_llm=False,
        )

    if use_llm:
        context = "\n".join(f"[{c.title or c.doc_id} · {nid}] {text}" for c, nid, text, _ in hits)
        resp = await llm.complete(
            system=ANSWER_SYSTEM, user=f"Question: {question}\n\nExcerpts:\n{context}"
        )
        if resp.text.strip():
            return NotebookAnswer(answer=resp.text.strip(), citations=citations, used_llm=True)

    extractive = " ".join(text for _, _, text, _ in hits)
    return NotebookAnswer(answer=extractive, citations=citations, used_llm=False)
