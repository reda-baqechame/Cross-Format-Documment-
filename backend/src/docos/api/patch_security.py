"""Security validation shared by direct and stored document patch entrypoints."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException

from docos.model.patch import Patch

_IMAGE_BLOB_OPS = frozenset({"insert_image", "replace_image", "set_image_attrs"})


def validate_image_blob_refs(doc_id: str, ops: Iterable[Patch]) -> None:
    """Allow request-selected image bytes only from this document's upload namespace.

    Parsed images already present in a canonical model remain valid. This check applies
    only when an incoming operation selects or replaces ``blob_ref``.
    """

    prefix = f"assets/{doc_id}/"
    for op in ops:
        if op.op not in _IMAGE_BLOB_OPS or "blob_ref" not in op.payload:
            continue
        ref = op.payload.get("blob_ref")
        if not isinstance(ref, str) or not ref.startswith(prefix) or ".." in ref.split("/"):
            raise HTTPException(
                status_code=422,
                detail="image blob_ref must reference an asset uploaded to this document",
            )
