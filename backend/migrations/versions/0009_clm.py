"""CLM: clause library + renewal reminders

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clauses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clauses_owner_session_id", "clauses", ["owner_session_id"])
    op.create_index("ix_clauses_owner_user_id", "clauses", ["owner_user_id"])

    op.create_table(
        "renewal_reminders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("doc_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("due_date", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_renewal_reminders_owner_session_id", "renewal_reminders", ["owner_session_id"]
    )
    op.create_index("ix_renewal_reminders_owner_user_id", "renewal_reminders", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_renewal_reminders_owner_user_id", table_name="renewal_reminders")
    op.drop_index("ix_renewal_reminders_owner_session_id", table_name="renewal_reminders")
    op.drop_table("renewal_reminders")
    op.drop_index("ix_clauses_owner_user_id", table_name="clauses")
    op.drop_index("ix_clauses_owner_session_id", table_name="clauses")
    op.drop_table("clauses")
