"""bulk send: bulk_send_packets

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bulk_send_packets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("source_doc_id", sa.String(), nullable=False),
        sa.Column("recipient", sa.String(), nullable=False),
        sa.Column("packet_doc_id", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bulk_send_packets_batch_id", "bulk_send_packets", ["batch_id"])
    op.create_index(
        "ix_bulk_send_packets_source_doc_id", "bulk_send_packets", ["source_doc_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_bulk_send_packets_source_doc_id", table_name="bulk_send_packets")
    op.drop_index("ix_bulk_send_packets_batch_id", table_name="bulk_send_packets")
    op.drop_table("bulk_send_packets")
