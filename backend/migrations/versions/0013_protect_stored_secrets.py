"""Protect stored OAuth and portal bearer credentials.

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_shares", sa.Column("token_ciphertext", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_shares", "token_ciphertext")
