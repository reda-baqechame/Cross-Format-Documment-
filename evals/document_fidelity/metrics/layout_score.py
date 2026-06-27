"""Layout-preservation metric.

Scores how well a parse preserved document structure: do top-level blocks carry an explicit
reading order, and is that order monotonic (not scrambled)? Returns a value in ``[0, 1]``.
"""

from __future__ import annotations

from typing import Any


def layout_score(doc: Any) -> float:
    """Average of reading-order *coverage* and *monotonicity* over the root's children."""
    root = doc.nodes.get(doc.root_id)
    if root is None:
        return 0.0
    top = [doc.nodes[c] for c in root.children if c in doc.nodes]
    if not top:
        return 1.0
    with_order = [n for n in top if n.reading_order is not None]
    coverage = len(with_order) / len(top)
    orders = [n.reading_order for n in with_order]
    monotonic = all(a <= b for a, b in zip(orders, orders[1:])) if orders else True
    return round(0.5 * coverage + 0.5 * (1.0 if monotonic else 0.0), 3)
