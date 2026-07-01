"""Expert packet audit tables.

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Idempotent: an interrupted SQLite replay may create a table without advancing the
    # Alembic stamp, so each CREATE IF NOT EXISTS-style guard keeps replay safe.
    if not _has_table("packets"):
        op.create_table(
            "packets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("pack", sa.String(), nullable=False),
            sa.Column("owner_session_id", sa.String(), nullable=True),
            sa.Column("owner_user_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_packets_owner_session_id", "packets", ["owner_session_id"])
        op.create_index("ix_packets_owner_user_id", "packets", ["owner_user_id"])

    if not _has_table("packet_documents"):
        op.create_table(
            "packet_documents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("packet_id", sa.String(), sa.ForeignKey("packets.id"), nullable=False),
            sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_packet_documents_packet_id", "packet_documents", ["packet_id"])
        op.create_index("ix_packet_documents_document_id", "packet_documents", ["document_id"])

    if not _has_table("packet_audit_runs"):
        op.create_table(
            "packet_audit_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("packet_id", sa.String(), sa.ForeignKey("packets.id"), nullable=False),
            sa.Column("pack", sa.String(), nullable=False),
            sa.Column("verdict", sa.String(), nullable=False),
            sa.Column("readiness_score", sa.Integer(), nullable=False),
            sa.Column("report", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_packet_audit_runs_packet_id", "packet_audit_runs", ["packet_id"])


def downgrade() -> None:
    if _has_table("packet_audit_runs"):
        op.drop_index("ix_packet_audit_runs_packet_id", table_name="packet_audit_runs")
        op.drop_table("packet_audit_runs")
    if _has_table("packet_documents"):
        op.drop_index("ix_packet_documents_packet_id", table_name="packet_documents")
        op.drop_index("ix_packet_documents_document_id", table_name="packet_documents")
        op.drop_table("packet_documents")
    if _has_table("packets"):
        op.drop_index("ix_packets_owner_session_id", table_name="packets")
        op.drop_index("ix_packets_owner_user_id", table_name="packets")
        op.drop_table("packets")
