"""Relevance retrieval over the canonical model (pure-Python BM25, no dependencies).

The AI editing path can only send the model a bounded slice of a document. Sending the *first* N
nodes (the old behaviour) is blind on long files — the relevant clause/row may be on page 40. This
ranks the document's editable nodes against the user's instruction with BM25 and returns the most
relevant ids, so the model sees the right context regardless of where it lives.

BM25 is implemented inline (a few lines of standard term-frequency math) to avoid a new dependency.
It is deterministic and redaction-aware: redacted nodes are never shown to the model.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from docos.model.document import CanonicalDocument
from docos.model.nodes import BaseNode
from docos.services.docengine.writers.redaction import is_redacted

_TOKEN = re.compile(r"[a-z0-9]+")
_K1 = 1.5
_B = 0.75
# Node types worth ranking + showing the model (text-bearing, editable).
_RANKABLE = ("run", "heading", "table_cell")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def node_search_text(doc: CanonicalDocument, node: BaseNode) -> str:
    """A node's searchable text: its own run text, or the joined text of its descendant runs."""
    if node.type == "run":
        return getattr(node, "text", "") or ""
    parts: list[str] = []
    for cid in node.children:
        child = doc.nodes.get(cid)
        if child is None:
            continue
        if child.type == "run":
            parts.append(getattr(child, "text", "") or "")
        else:
            parts.append(node_search_text(doc, child))
    return " ".join(parts)


def _candidates(doc: CanonicalDocument) -> list[tuple[BaseNode, list[str]]]:
    out: list[tuple[BaseNode, list[str]]] = []
    for node in doc.walk():
        if node.type not in _RANKABLE or is_redacted(doc, node.id):
            continue
        tokens = _tokenize(node_search_text(doc, node))
        if tokens:
            out.append((node, tokens))
    return out


def bm25_scores(
    corpus_tokens: list[list[str]], query_terms: set[str], *, k1: float = _K1, b: float = _B
) -> list[float]:
    """BM25 relevance score per document, given pre-tokenized docs + a query term set.

    Tokenizer-agnostic (callers supply their own tokenization), so node-level retrieval and
    corpus-level library search share one implementation. Returns a score aligned to
    ``corpus_tokens`` (0.0 where nothing matches).
    """
    n = len(corpus_tokens)
    if n == 0 or not query_terms:
        return [0.0] * n
    avgdl = (sum(len(toks) for toks in corpus_tokens) / n) or 1.0
    df: Counter = Counter()
    for toks in corpus_tokens:
        present = set(toks)
        for term in query_terms:
            if term in present:
                df[term] += 1

    scores: list[float] = []
    for toks in corpus_tokens:
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for term in query_terms:
            f = tf.get(term, 0)
            if f == 0:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(score)
    return scores


def rank_nodes(doc: CanonicalDocument, query: str, *, k: int = 200) -> list[str]:
    """Return up to ``k`` node ids most relevant to ``query`` (BM25), best first.

    An empty/whitespace query (or a query with no usable terms) falls back to document order, so the
    caller always gets a sensible slice.
    """
    candidates = _candidates(doc)
    if not candidates:
        return []
    q_terms = set(_tokenize(query))
    if not q_terms:
        return [node.id for node, _ in candidates[:k]]

    scores = bm25_scores([toks for _, toks in candidates], q_terms)
    # Highest score first; ties keep document order (stable, deterministic).
    scored = [
        (scores[i], i, candidates[i][0].id) for i in range(len(candidates)) if scores[i] > 0
    ]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [nid for _, _, nid in scored[:k]]


def select_digest_nodes(doc: CanonicalDocument, instruction: str, *, limit: int) -> list[str]:
    """Pick which node ids to put in the model's digest, in document order.

    Small documents are shown whole (up to ``limit``). Large ones are narrowed to the BM25-relevant
    nodes for the instruction, then re-sorted into document order so the model reads them naturally.
    Redacted nodes are always excluded.
    """
    candidates = [node for node, _ in _candidates(doc)]
    if len(candidates) <= limit:
        return [n.id for n in candidates[:limit]]
    relevant = set(rank_nodes(doc, instruction, k=limit))
    return [n.id for n in candidates if n.id in relevant]
