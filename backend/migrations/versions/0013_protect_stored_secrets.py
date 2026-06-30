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


def _has_token_ciphertext() -> bool:
    columns = sa.inspect(op.get_bind()).get_columns("document_shares")
    return any(column["name"] == "token_ciphertext" for column in columns)


def upgrade() -> None:
    # See 0012: an interrupted SQLite migration may apply the ALTER TABLE but
    # not advance Alembic's version stamp. Replaying must be safe.
    if not _has_token_ciphertext():
        op.add_column(
            "document_shares", sa.Column("token_ciphertext", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    if _has_token_ciphertext():
        op.drop_column("document_shares", "token_ciphertext")
