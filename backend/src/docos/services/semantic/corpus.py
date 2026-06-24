"""Corpus-level intelligence: semantic search and a multi-document notebook.

Both run over the canonical models of *many* documents at once and stay fully
deterministic and offline (no embeddings service required): ranking is TF-IDF cosine
similarity, which captures semantic relevance — a query for "salary" surfaces a doc
about "compensation" via shared rarer terms — without a network call. A configured LLM
provider, when present, only rephrases the same cited excerpts for the notebook answer.
"""

from __future__ import annotations

import math
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


def _idf(corpus_terms: list[set[str]]) -> dict[str, float]:
    n = len(corpus_terms)
    df: Counter[str] = Counter()
    for terms in corpus_terms:
        df.update(terms)
    # Smoothed idf so a term in every doc still has a small positive weight.
    return {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}


def _tfidf_vec(counts: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    return {t: tf * idf.get(t, 0.0) for t, tf in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _best_snippet(doc: CanonicalDocument, query_terms: set[str]) -> str:
    best_text, best_score = "", -1
    for _node_id, text in _text_nodes(doc):
        score = len(query_terms & set(_term_counts(text)))
        if score > best_score:
            best_text, best_score = text, score
    return _excerpt(best_text) if best_text else ""


def semantic_search(corpus: list[CorpusDoc], query: str, limit: int = 20) -> list[SemanticHit]:
    """Rank documents by TF-IDF cosine similarity to ``query`` (most relevant first)."""
    if not corpus:
        return []
    doc_counts = [_term_counts(_doc_text(c.doc)) for c in corpus]
    idf = _idf([set(c) for c in doc_counts])
    qvec = _tfidf_vec(_term_counts(query), idf)
    if not qvec:
        return []
    query_terms = set(_term_counts(query))

    scored: list[SemanticHit] = []
    for c, counts in zip(corpus, doc_counts, strict=True):
        score = _cosine(qvec, _tfidf_vec(counts, idf))
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
