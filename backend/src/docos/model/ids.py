"""Stable node-id generation.

Node ids are stable for the lifetime of a document so that reversible patches can
target nodes unambiguously across versions.
"""

from __future__ import annotations

import uuid


def new_node_id(prefix: str = "n") -> str:
    """Return a fresh, collision-resistant node id, e.g. ``"n_3f2a..."``."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def new_doc_id() -> str:
    return f"doc_{uuid.uuid4().hex[:16]}"


def new_patch_id() -> str:
    return f"patch_{uuid.uuid4().hex[:12]}"
