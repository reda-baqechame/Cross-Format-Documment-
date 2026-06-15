"""Serialization and canonical hashing for the document model.

The JSON form is what gets stored in Postgres JSONB and shipped to the frontend.
The canonical hash is a content fingerprint used to identify versions and detect
drift; it must be stable regardless of dict ordering.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from docos.model.document import CanonicalDocument


def to_dict(doc: CanonicalDocument) -> dict[str, Any]:
    """Serialize to a plain JSON-able dict (datetimes -> ISO strings)."""
    return doc.model_dump(mode="json")


def from_dict(data: dict[str, Any]) -> CanonicalDocument:
    """Rehydrate a document from its serialized form."""
    return CanonicalDocument.model_validate(data)


def canonical_hash(doc: CanonicalDocument) -> str:
    """Return a stable SHA-256 over the document content.

    ``content_hash`` itself is excluded so a document's hash does not depend on a
    previously stored hash.
    """
    payload = to_dict(doc)
    payload.pop("content_hash", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
