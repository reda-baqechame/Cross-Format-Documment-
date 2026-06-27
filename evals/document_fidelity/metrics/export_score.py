"""Export-openability metric.

Exports the document to plain text through the real adapter pipeline and measures (a) that the
output is non-empty/openable and (b) what fraction of the document's visible words survived the
round-trip. Returns ``{"openable": bool, "text_retention": float}``.
"""

from __future__ import annotations

from typing import Any


def _visible_words(doc: Any) -> set[str]:
    from docos.services.docengine.writers.redaction import node_text

    words: set[str] = set()
    for node in doc.nodes.values():
        if node.type == "run":
            words.update(node_text(doc, node).split())
    return words


def export_score(doc: Any, registry: Any) -> dict[str, Any]:
    try:
        out = registry.resolve_by_format("txt").export(doc, target_mime="text/plain")
    except Exception:  # noqa: BLE001 - a failed export is simply a failing score
        out = b""
    text = out.decode("utf-8", errors="replace")
    expected = _visible_words(doc)
    retained = sum(1 for w in expected if w in text)
    ratio = retained / len(expected) if expected else 1.0
    return {"openable": len(out) > 0, "text_retention": round(ratio, 3)}
