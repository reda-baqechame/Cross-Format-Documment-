"""Unit tests for the retrieval benchmark metrics (recall@k, MRR, nDCG)."""

from __future__ import annotations

import sys
from pathlib import Path

_EVALS = Path(__file__).resolve().parents[2] / "evals"
sys.path.insert(0, str(_EVALS))

from search_retrieval.metrics import (  # noqa: E402
    LabeledQuery,
    aggregate,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_counts_relevant_in_topk():
    assert recall_at_k(["a", "b", "c"], frozenset({"a", "c"}), 3) == 1.0
    assert recall_at_k(["x", "y", "a"], frozenset({"a"}), 2) == 0.0
    assert recall_at_k(["x", "y", "a"], frozenset({"a"}), 3) == 1.0


def test_reciprocal_rank_is_inverse_of_first_hit():
    assert reciprocal_rank(["a", "b"], frozenset({"a"})) == 1.0
    assert reciprocal_rank(["x", "a"], frozenset({"a"})) == 0.5
    assert reciprocal_rank(["x", "y"], frozenset({"a"})) == 0.0


def test_ndcg_rewards_higher_rank():
    top = ndcg_at_k(["a", "x", "y"], frozenset({"a"}), 3)
    low = ndcg_at_k(["x", "y", "a"], frozenset({"a"}), 3)
    assert top == 1.0
    assert low < top


def test_aggregate_means_across_queries():
    q = LabeledQuery("q", frozenset({"a"}), "lexical")
    out = aggregate([(q, ["a"]), (q, ["x", "a"])], k=5)
    assert out["n"] == 2
    assert out["recall_at_k"] == 1.0
    assert out["mrr"] == 0.75  # (1.0 + 0.5) / 2
