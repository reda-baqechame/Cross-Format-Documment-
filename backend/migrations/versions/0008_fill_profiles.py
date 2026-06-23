"""fill profiles (Fill Once)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fill_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_fill_profiles_owner_session_id", "fill_profiles", ["owner_session_id"]
    )
    op.create_index("ix_fill_profiles_owner_user_id", "fill_profiles", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_fill_profiles_owner_user_id", table_name="fill_profiles")
    op.drop_index("ix_fill_profiles_owner_session_id", table_name="fill_profiles")
    op.drop_table("fill_profiles")
