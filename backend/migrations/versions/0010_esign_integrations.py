"""e-signature requests + cloud integration tokens (gated provider seams)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signature_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("signers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_signature_requests_owner_session_id", "signature_requests", ["owner_session_id"]
    )
    op.create_index(
        "ix_signature_requests_owner_user_id", "signature_requests", ["owner_user_id"]
    )

    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_integration_tokens_owner_session_id", "integration_tokens", ["owner_session_id"]
    )
    op.create_index(
        "ix_integration_tokens_owner_user_id", "integration_tokens", ["owner_user_id"]
    )
    op.create_index("ix_integration_tokens_provider", "integration_tokens", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_integration_tokens_provider", table_name="integration_tokens")
    op.drop_index("ix_integration_tokens_owner_user_id", table_name="integration_tokens")
    op.drop_index("ix_integration_tokens_owner_session_id", table_name="integration_tokens")
    op.drop_table("integration_tokens")
    op.drop_index("ix_signature_requests_owner_user_id", table_name="signature_requests")
    op.drop_index("ix_signature_requests_owner_session_id", table_name="signature_requests")
    op.drop_table("signature_requests")
