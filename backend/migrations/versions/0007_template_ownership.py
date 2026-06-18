"""template ownership

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("templates", sa.Column("owner_session_id", sa.String(), nullable=True))
    op.add_column("templates", sa.Column("owner_user_id", sa.String(), nullable=True))
    op.create_index("ix_templates_owner_session_id", "templates", ["owner_session_id"])
    op.create_index("ix_templates_owner_user_id", "templates", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_templates_owner_user_id", table_name="templates")
    op.drop_index("ix_templates_owner_session_id", table_name="templates")
    op.drop_column("templates", "owner_user_id")
    op.drop_column("templates", "owner_session_id")
