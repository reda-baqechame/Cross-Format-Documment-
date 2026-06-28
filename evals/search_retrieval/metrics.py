"""Retrieval metrics — recall@k, MRR, nDCG@k — over a labeled query set.

Deterministic, dependency-free. ``ranked`` is the list of doc_ids a search returned (best first);
``relevant`` is the set of doc_ids judged relevant for that query.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LabeledQuery:
    query: str
    relevant: frozenset[str]
    # "lexical" = the query shares words with the target (BM25 should find it).
    # "semantic" = the query only shares *meaning* (synonyms/paraphrase) — the lexical gap.
    kind: str


def recall_at_k(ranked: list[str], relevant: frozenset[str], k: int) -> float:
    if not relevant:
        return 1.0
    hit = sum(1 for d in ranked[:k] if d in relevant)
    return hit / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: frozenset[str]) -> float:
    for i, d in enumerate(ranked, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: frozenset[str], k: int) -> float:
    dcg = 0.0
    for i, d in enumerate(ranked[:k], start=1):
        if d in relevant:
            dcg += 1.0 / math.log2(i + 1)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 1.0


def aggregate(results: list[tuple[LabeledQuery, list[str]]], *, k: int) -> dict[str, float]:
    """Mean metrics across queries. Returns recall@k, mrr, ndcg@k (rounded)."""
    if not results:
        return {"recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0, "n": 0}
    n = len(results)
    recall = sum(recall_at_k(r, q.relevant, k) for q, r in results) / n
    mrr = sum(reciprocal_rank(r, q.relevant) for q, r in results) / n
    ndcg = sum(ndcg_at_k(r, q.relevant, k) for q, r in results) / n
    return {
        "recall_at_k": round(recall, 4),
        "mrr": round(mrr, 4),
        "ndcg_at_k": round(ndcg, 4),
        "n": n,
    }
