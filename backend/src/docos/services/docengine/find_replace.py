"""Find & replace over the canonical model.

A deterministic, offline capability implemented once over the document graph so it
works for every format. It rewrites the text of matching ``run`` nodes; the route
turns the planned changes into ``set_text`` ops that flow through the normal
apply → commit → audit path, so a replace-all is reversible and versioned like any
other edit. Redacted runs are skipped — their text is removed on export and must not
be surfaced or rewritten here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted


@dataclass(frozen=True)
class Replacement:
    """A single run whose text changed, and how many matches it contained."""

    node_id: str
    before: str
    after: str
    count: int


def plan_find_replace(
    doc: CanonicalDocument,
    find: str,
    replace: str,
    *,
    match_case: bool = False,
    whole_word: bool = False,
) -> tuple[list[Replacement], int]:
    """Plan a replace-all over every non-redacted run.

    Returns the per-run replacements and the total number of occurrences. The
    replacement string is treated literally (no regex backreferences).
    """
    if not find:
        return [], 0

    flags = 0 if match_case else re.IGNORECASE
    pattern = re.escape(find)
    if whole_word:
        pattern = rf"\b{pattern}\b"
    rx = re.compile(pattern, flags)

    replacements: list[Replacement] = []
    total = 0
    for node in doc.nodes.values():
        if node.type != "run" or is_redacted(doc, node.id):
            continue
        text = getattr(node, "text", "") or ""
        matches = len(rx.findall(text))
        if matches == 0:
            continue
        new_text = rx.sub(lambda _m: replace, text)
        replacements.append(
            Replacement(node_id=node.id, before=text, after=new_text, count=matches)
        )
        total += matches

    return replacements, total
