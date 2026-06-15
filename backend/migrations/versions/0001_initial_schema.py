"""initial schema: documents, versions, audit events, labels, jobs

Revision ID: 0001
Revises:
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("source_format", sa.String(), nullable=False),
        sa.Column("source_mime", sa.String(), nullable=False),
        sa.Column("blob_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_version_id", sa.String(), nullable=True),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("model", sa.JSON(), nullable=False),
        sa.Column("patch_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("labels")
    op.drop_table("audit_events")
    op.drop_table("document_versions")
    op.drop_table("documents")
