"""OCR-confidence metric.

Averages the per-run OCR confidence (0–100, stored in ``attrs["confidence"]`` by the OCR engines)
and normalises to ``[0, 1]``. A document with no OCR runs scores 1.0 (nothing uncertain to weigh).
"""

from __future__ import annotations

from typing import Any


def ocr_score(doc: Any) -> float:
    confs = [
        n.attrs["confidence"]
        for n in doc.nodes.values()
        if n.type == "run" and isinstance(n.attrs.get("confidence"), (int, float))
    ]
    if not confs:
        return 1.0
    return round((sum(confs) / len(confs)) / 100.0, 3)
