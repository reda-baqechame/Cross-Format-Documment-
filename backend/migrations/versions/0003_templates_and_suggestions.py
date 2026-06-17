"""templates library + suggested edits (track-changes)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_doc_id", sa.String(), nullable=True),
        sa.Column("source_format", sa.String(), nullable=False),
        sa.Column("model", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "suggested_edits",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("patch", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("new_version_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_suggested_edits_document_id", "suggested_edits", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_suggested_edits_document_id", table_name="suggested_edits")
    op.drop_table("suggested_edits")
    op.drop_table("templates")
