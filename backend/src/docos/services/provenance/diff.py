"""Document comparison — a redline/diff over two canonical models.

Because every format parses into the same node graph, this one implementation compares
any document against any other (PDF vs DOCX, v1 vs v2) — the cross-format compare the
dedicated tools (Draftable, Litera Compare) can't do without format-specific engines.
The diff is block-level (paragraphs/headings/list items) using difflib, honoring
redaction so removed content isn't leaked through a comparison.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import run_text

_BLOCK_TYPES = ("heading", "paragraph", "list_item", "table_cell")

DiffOp = Literal["equal", "insert", "delete", "replace"]


class DiffSegment(BaseModel):
    op: DiffOp
    a_text: str | None = None  # content in the base document
    b_text: str | None = None  # content in the compared document


class DiffResult(BaseModel):
    segments: list[DiffSegment]
    added: int
    removed: int
    changed: int
    unchanged: int


def block_texts(doc: CanonicalDocument) -> list[str]:
    """Non-empty block-level text, in reading order (redaction-aware)."""
    out: list[str] = []
    for node in doc.walk():
        if node.type in _BLOCK_TYPES:
            text = "".join(
                run_text(doc, r) for r in doc.children_of(node.id) if r.type == "run"
            ).strip()
            if text:
                out.append(text)
    return out


def diff_documents(base: CanonicalDocument, other: CanonicalDocument) -> DiffResult:
    a, b = block_texts(base), block_texts(other)
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    segments: list[DiffSegment] = []
    added = removed = changed = unchanged = 0

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for k in range(i1, i2):
                segments.append(DiffSegment(op="equal", a_text=a[k], b_text=a[k]))
            unchanged += i2 - i1
        elif op == "insert":
            for k in range(j1, j2):
                segments.append(DiffSegment(op="insert", b_text=b[k]))
            added += j2 - j1
        elif op == "delete":
            for k in range(i1, i2):
                segments.append(DiffSegment(op="delete", a_text=a[k]))
            removed += i2 - i1
        elif op == "replace":
            # Pair the changed lines positionally; surplus on either side is add/remove.
            span = max(i2 - i1, j2 - j1)
            for n in range(span):
                ai = i1 + n
                bj = j1 + n
                segments.append(
                    DiffSegment(
                        op="replace",
                        a_text=a[ai] if ai < i2 else None,
                        b_text=b[bj] if bj < j2 else None,
                    )
                )
            changed += span

    return DiffResult(
        segments=segments, added=added, removed=removed, changed=changed, unchanged=unchanged
    )
