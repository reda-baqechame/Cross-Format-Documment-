"""ORM models.

The serialized canonical model lives in ``DocumentVersion.model`` (JSONB), so every
version is a full, addressable snapshot. ``AuditEvent`` is append-only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docos.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    source_format: Mapped[str] = mapped_column(String)
    source_mime: Mapped[str] = mapped_column(String)
    blob_key: Mapped[str] = mapped_column(String)  # original uploaded bytes
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    current_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Ownership: an anonymous session owns the document; a registered user can later claim it.
    # NULL owner = orphaned/legacy and inaccessible to any session (see api/access.py).
    owner_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # = content hash
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[dict] = mapped_column(JSON)  # serialized CanonicalDocument
    patch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped[Document] = relationship(back_populates="versions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="system")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    label: Mapped[str] = mapped_column(String)  # e.g. "Confidential", "PII"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ApprovalStep(Base):
    """One approver's step in a document's approval / multi-party signing workflow.

    A workflow is the set of steps sharing a ``workflow_id``. ``order_index`` defines the
    signing order; ``status`` is pending | approved | rejected. State lives in rows (not the
    versioned model) because it is workflow metadata about the document, not its content.
    """

    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String)
    order_index: Mapped[int] = mapped_column(Integer)
    approver: Mapped[str] = mapped_column(String)
    ordered: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Template(Base):
    """A reusable document template — a stored canonical-model snapshot.

    ``model`` is a serialized :class:`CanonicalDocument`; instantiating a template
    regenerates ids into a brand-new document (see ``services/templates``). State lives
    in its own table because a template is a library asset, not a versioned document.
    """

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_format: Mapped[str] = mapped_column(String, default="txt")
    owner_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    model: Mapped[dict] = mapped_column(JSON)  # serialized CanonicalDocument snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SuggestedEdit(Base):
    """A proposed (not-yet-applied) reversible patch — track-changes / suggest mode.

    A suggestion stores a :class:`ReversiblePatch` payload as JSON. Accepting it runs the
    patch through the normal apply → commit_version → audit path; rejecting it just marks
    the row. Pending suggestions never alter the document, so review is non-destructive.
    """

    __tablename__ = "suggested_edits"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    patch: Mapped[dict] = mapped_column(JSON)  # serialized ReversiblePatch (forward ops)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|accepted|rejected
    new_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BulkSendPacket(Base):
    """One recipient's copy in a bulk-send batch (one packet → many recipients).

    Bulk send stamps out an independent document copy per recipient and starts a
    single-approver workflow on each, so recipients act on their own packet without
    seeing each other. Rows sharing a ``batch_id`` form one send.
    """

    __tablename__ = "bulk_send_packets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    source_doc_id: Mapped[str] = mapped_column(String, index=True)
    recipient: Mapped[str] = mapped_column(String)
    packet_doc_id: Mapped[str] = mapped_column(String)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EditorSession(Base):
    """An embedded editor handoff session for native DOCX/XLSX/PPTX/PDF editing.

    The row is deliberately provider-neutral: local/basic sessions work immediately,
    while ONLYOFFICE or licensed PDF SDK sessions can attach provider config without
    changing the public API.
    """

    __tablename__ = "editor_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    provider: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="edit")
    status: Mapped[str] = mapped_column(String, default="created")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    saved_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)  # ingest | ocr | apply_patch
    document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)


class BlobTombstone(Base):
    """A blob whose deletion failed — retry seam so deleted bytes don't silently linger.

    When a document is deleted but its blob delete fails, we record the failure here (instead
    of swallowing it) and audit it. A future sweeper retries ``blob_store.delete`` and flips
    ``resolved``, so the platform can prove storage actually drained.
    """

    __tablename__ = "blob_tombstones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blob_key: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(String, default="delete_failed")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class FillProfile(Base):
    """A reusable set of field-name → value answers for one-click form autofill ("Fill Once").

    Keyed to the session (same anonymous-owner model as documents/templates), so a user enters
    their details once and any later form's matching fields auto-populate. Stores the user's own
    answers, never document content.
    """

    __tablename__ = "fill_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # field-name (lowercased) → value
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Clause(Base):
    """A reusable contract clause in the caller's library (CLM).

    Session-scoped like templates/profiles. Saving stores the clause text; inserting it into a
    document is an ordinary reversible ``add_node`` patch, so the insertion is versioned + audited.
    """

    __tablename__ = "clauses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class RenewalReminder(Base):
    """An in-app renewal/expiry reminder for a contract (CLM).

    Tracks a due date and note, optionally linked to a document. Reminders are session-scoped and
    surfaced in-app, sorted by due date — there is no email/push delivery (that needs infra).
    """

    __tablename__ = "renewal_reminders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    doc_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    due_date: Mapped[str] = mapped_column(String)  # ISO YYYY-MM-DD (sorts chronologically)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
