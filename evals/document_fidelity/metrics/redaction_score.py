"""Redaction-unrecoverability metric.

The product promise is that redaction *removes* content. This metric marks the run carrying a secret
as redacted, exports through the real pipeline, and verifies the secret is absent from the output
bytes. Returns 1.0 when the secret is truly gone, 0.0 if it leaked.
"""

from __future__ import annotations

from typing import Any


def redaction_score(doc: Any, registry: Any, *, secret: str) -> float:
    target = next(
        (n for n in doc.nodes.values() if n.type == "run" and secret in getattr(n, "text", "")),
        None,
    )
    if target is None:
        return 1.0  # nothing to redact in this sample
    probe = doc.model_copy(deep=True)
    if target.id not in probe.redaction.redacted_node_ids:
        probe.redaction.redacted_node_ids.append(target.id)
    try:
        out = registry.resolve_by_format("txt").export(probe, target_mime="text/plain")
    except Exception:  # noqa: BLE001 - a failed export can't prove removal
        return 0.0
    return 1.0 if secret not in out.decode("utf-8", errors="replace") else 0.0
