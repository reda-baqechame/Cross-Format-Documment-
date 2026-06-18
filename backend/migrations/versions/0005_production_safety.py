"""production safety: document ownership + blob tombstones

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-session ownership so anonymous visitors get a private workspace (no cross-user IDOR).
    op.add_column("documents", sa.Column("owner_session_id", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("owner_user_id", sa.String(), nullable=True))
    op.create_index("ix_documents_owner_session_id", "documents", ["owner_session_id"])
    op.create_index("ix_documents_owner_user_id", "documents", ["owner_user_id"])

    # Durable record of failed blob deletions (no more silently-swallowed cleanup errors).
    op.create_table(
        "blob_tombstones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("blob_key", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_blob_tombstones_blob_key", "blob_tombstones", ["blob_key"])


def downgrade() -> None:
    op.drop_index("ix_blob_tombstones_blob_key", table_name="blob_tombstones")
    op.drop_table("blob_tombstones")
    op.drop_index("ix_documents_owner_user_id", table_name="documents")
    op.drop_index("ix_documents_owner_session_id", table_name="documents")
    op.drop_column("documents", "owner_user_id")
    op.drop_column("documents", "owner_session_id")
