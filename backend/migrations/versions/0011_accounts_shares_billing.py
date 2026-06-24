"""Users, document shares, and subscriptions for accounts + portal + billing.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "document_shares",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("permission", sa.String(), nullable=False, server_default="view"),
        sa.Column("pin_hash", sa.String(), nullable=True),
        sa.Column("recipient_label", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_shares_token", "document_shares", ["token"], unique=True)
    op.create_index("ix_document_shares_document_id", "document_shares", ["document_id"])
    op.create_index(
        "ix_document_shares_owner_session_id", "document_shares", ["owner_session_id"]
    )
    op.create_index("ix_document_shares_owner_user_id", "document_shares", ["owner_user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_document_shares_owner_user_id", table_name="document_shares")
    op.drop_index("ix_document_shares_owner_session_id", table_name="document_shares")
    op.drop_index("ix_document_shares_document_id", table_name="document_shares")
    op.drop_index("ix_document_shares_token", table_name="document_shares")
    op.drop_table("document_shares")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
