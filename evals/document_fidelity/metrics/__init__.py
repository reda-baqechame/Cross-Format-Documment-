"""Deterministic document-fidelity metrics.

Each metric is a pure function over a :class:`CanonicalDocument` (and, where relevant, the adapter
registry it can export through). No LLM and no network: the lab measures the *plumbing* — parse
fidelity, OCR confidence, table structure, export openability, and redaction unrecoverability — so
extraction quality is engineered against numbers instead of guessed.
"""

from .export_score import export_score
from .layout_score import layout_score
from .ocr_score import ocr_score
from .redaction_score import redaction_score
from .table_score import table_score

__all__ = [
    "export_score",
    "layout_score",
    "ocr_score",
    "redaction_score",
    "table_score",
]
