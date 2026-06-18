"""editor sessions for native editor providers

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "editor_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("saved_version_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_editor_sessions_document_id", "editor_sessions", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_editor_sessions_document_id", table_name="editor_sessions")
    op.drop_table("editor_sessions")
