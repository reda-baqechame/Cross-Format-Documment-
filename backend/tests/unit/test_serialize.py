"""Canonical model round-trips and hashes deterministically."""

from __future__ import annotations

from docos.model.serialize import canonical_hash, from_dict, to_dict
from docos.services.docengine.adapters.txt import TxtAdapter


def _doc():
    return TxtAdapter().parse(b"Hello\n\nWorld")


def test_round_trip_preserves_document():
    doc = _doc()
    restored = from_dict(to_dict(doc))
    assert restored.doc_id == doc.doc_id
    assert restored.root_id == doc.root_id
    assert set(restored.nodes) == set(doc.nodes)


def test_canonical_hash_is_stable_and_order_independent():
    doc = _doc()
    h1 = canonical_hash(doc)
    h2 = canonical_hash(from_dict(to_dict(doc)))
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_hash_ignores_existing_content_hash():
    doc = _doc()
    base = canonical_hash(doc)
    doc.content_hash = "sha256:deadbeef"
    assert canonical_hash(doc) == base
