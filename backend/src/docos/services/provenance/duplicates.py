"""Near-duplicate document detection (rapidfuzz, MIT).

Finds documents that are the same or near-identical — duplicate invoices, re-uploaded contracts,
copies with trivial edits — by comparing their normalized text with rapidfuzz's token-sort ratio and
clustering the matches. Pure functions over text so they are deterministic and unit-testable; the
route layer supplies the per-document text.
"""

from __future__ import annotations

from pydantic import BaseModel
from rapidfuzz import fuzz

from docos.model.document import CanonicalDocument

# Default similarity (0–1) at/above which two documents are considered near-duplicates.
DEFAULT_THRESHOLD = 0.9


class DuplicateGroup(BaseModel):
    """A cluster of near-identical documents."""

    doc_ids: list[str]
    titles: list[str]
    similarity: float  # the lowest pairwise similarity within the group (conservative)


def document_text(doc: CanonicalDocument) -> str:
    """Concatenated run text of a document, for similarity comparison."""
    parts = [
        getattr(n, "text", "")
        for n in doc.nodes.values()
        if n.type == "run" and getattr(n, "text", "")
    ]
    return " ".join(parts)


def similarity(a: str, b: str) -> float:
    """Token-sort similarity of two texts in ``[0, 1]`` (order-insensitive)."""
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b) / 100.0


def group_duplicates(
    items: list[tuple[str, str]], *, threshold: float = DEFAULT_THRESHOLD
) -> list[DuplicateGroup]:
    """Cluster ``(doc_id, text)`` items into near-duplicate groups via union-find.

    Returns only groups with 2+ members. Each group's ``similarity`` is the minimum pairwise score
    among its members, so a high number means "every doc in here is very close to every other".
    """
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pair_scores: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = similarity(items[i][1], items[j][1])
            if s >= threshold:
                parent[find(i)] = find(j)
                pair_scores[(i, j)] = s

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    groups: list[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        sims = [
            pair_scores.get((min(a, b), max(a, b)), 0.0)
            for a in members
            for b in members
            if a < b
        ]
        groups.append(
            DuplicateGroup(
                doc_ids=[items[m][0] for m in members],
                titles=[],  # filled in by the route from the Document records
                similarity=round(min(sims), 3) if sims else 1.0,
            )
        )
    return groups
