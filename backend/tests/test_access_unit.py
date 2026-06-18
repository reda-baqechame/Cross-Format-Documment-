"""Unit tests for the ownership authorization helper."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from docos.api.access import claim_documents, get_owned_document, owns
from docos.api.session import Actor
from docos.db.models import Document


def _doc(**kw) -> Document:
    return Document(
        id=kw.get("id", "doc1"),
        title="t",
        source_format="txt",
        source_mime="text/plain",
        blob_key="",
        owner_session_id=kw.get("owner_session_id"),
        owner_user_id=kw.get("owner_user_id"),
    )


def test_owns_by_session():
    assert owns(_doc(owner_session_id="s1"), Actor(session_id="s1")) is True
    assert owns(_doc(owner_session_id="s1"), Actor(session_id="s2")) is False


def test_owns_by_claimed_user():
    rec = _doc(owner_session_id="s1", owner_user_id="u1")
    # A different session, but the same authenticated user, retains access.
    assert owns(rec, Actor(session_id="other", user_id="u1")) is True


def test_null_owner_is_inaccessible():
    assert owns(_doc(owner_session_id=None), Actor(session_id="s1")) is False


def test_get_owned_document_unit(db):
    db.add(_doc(id="d1", owner_session_id="s1"))
    db.commit()

    assert get_owned_document(db, "d1", Actor(session_id="s1")).id == "d1"
    with pytest.raises(HTTPException) as exc:
        get_owned_document(db, "d1", Actor(session_id="s2"))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        get_owned_document(db, "missing", Actor(session_id="s1"))


def test_claim_documents_seam(db):
    db.add(_doc(id="d1", owner_session_id="s1"))
    db.add(_doc(id="d2", owner_session_id="s1"))
    db.commit()

    n = claim_documents(db, from_session="s1", to_user="u1")
    db.commit()
    assert n == 2
    assert owns(db.get(Document, "d1"), Actor(session_id="other", user_id="u1"))
