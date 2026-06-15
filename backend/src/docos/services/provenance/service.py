"""Concrete provenance & policy service over a SQLAlchemy session."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from docos.model.document import CanonicalDocument
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.provenance import audit, labels, versions
from docos.services.provenance.health import DocumentHealth, compute_health
from docos.services.provenance.interface import ProvenancePolicyService, VersionRef

_RISKY_META_KEYS = ("last_modified_by", "author", "comments", "revision")


class ProvenancePolicyServiceImpl(ProvenancePolicyService):
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_event(self, doc_id: str | None, action: str, *, actor: str, detail: dict) -> None:
        audit.write_event(self.session, doc_id, action, actor=actor, detail=detail)

    def commit_version(
        self, doc: CanonicalDocument, *, patch: ReversiblePatch | None = None
    ) -> str:
        lineage = versions.lineage(self.session, doc.doc_id)
        parent_id = lineage[-1].id if lineage else None
        return versions.commit(
            self.session, doc, parent_id=parent_id, patch_id=patch.id if patch else None
        )

    def history(self, doc_id: str) -> list[VersionRef]:
        return [
            VersionRef(
                version_id=v.id, parent_id=v.parent_id, patch_id=v.patch_id, created_at=v.created_at
            )
            for v in versions.lineage(self.session, doc_id)
        ]

    def compute_health(self, doc: CanonicalDocument) -> DocumentHealth:
        return compute_health(doc)

    def apply_label(self, doc_id: str, label: str) -> None:
        labels.add_label(self.session, doc_id, label)

    def sanitize_metadata(self, doc: CanonicalDocument) -> ReversiblePatch:
        """Reversible patch clearing risky embedded metadata keys."""
        before = {k: doc.meta.custom.get(k) for k in _RISKY_META_KEYS if doc.meta.custom.get(k)}
        forward = [
            Patch(op="update_node", target_id=doc.root_id, payload={"_clear_meta": list(before)})
        ]
        inverse = [
            Patch(op="update_node", target_id=doc.root_id, payload={"_restore_meta": before})
        ]
        return ReversiblePatch(
            id=new_patch_id(),
            patches=forward,
            inverse=inverse,
            intent="sanitize embedded metadata",
            created_at=datetime.now(timezone.utc),
        )
