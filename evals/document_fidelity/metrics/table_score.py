"""Table-extraction metric.

Compares the number of table cells recovered into the canonical model against the expected count,
returning the recall in ``[0, 1]``. A coarse but deterministic proxy for table-structure fidelity.
"""

from __future__ import annotations

from typing import Any


def table_score(doc: Any, *, expected_cells: int) -> float:
    cells = sum(1 for n in doc.nodes.values() if n.type == "table_cell")
    if expected_cells <= 0:
        return 1.0
    return round(min(cells, expected_cells) / expected_cells, 3)
