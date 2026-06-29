"""Shared helper: run a reversible patch through the standard apply → commit → audit path.

Several routers (patches, comments, …) build a :class:`ReversiblePatch` and then need
the exact same plumbing: apply it, commit a new version, repoint the document's current
version, and write an audit event. This keeps that single source of truth in one place.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from docos.api.session import Actor
from docos.db.models import Document
from docos.deps import get_orchestrator, get_provenance
from docos.model.document import CanonicalDocument
from docos.model.patch import ReversiblePatch


def apply_and_commit(
    session: Session,
    doc_id: str,
    doc: CanonicalDocument,
    patch: ReversiblePatch,
    *,
    actor: Actor,
    event: str,
    detail: dict | None = None,
) -> tuple[str | None, CanonicalDocument]:
    """Apply ``patch`` to ``doc``, persist a new version, audit it.

    Returns ``(new_version_id, updated_doc)``. If the patch has no ops, nothing is
    committed and ``(None, doc)`` is returned.
    """
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    if not patch.patches:
        provenance.record_event(
            doc_id,
            event,
            actor=actor.user_id or actor.session_id,
            detail={**(detail or {}), "applied": False},
        )
        session.commit()
        return None, doc

    updated = orchestrator.apply(doc, patch)
    new_version_id = provenance.commit_version(updated, patch=patch)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id
    provenance.record_event(
        doc_id,
        event,
        actor=actor.user_id or actor.session_id,
        detail={**(detail or {}), "patch_id": patch.id, "applied": True},
    )
    session.commit()
    return new_version_id, updated
