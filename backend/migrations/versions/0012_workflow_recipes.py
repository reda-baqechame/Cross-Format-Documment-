"""User-defined workflow recipes + run tracking (Phase H1).

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_recipes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False, server_default="manual"),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_recipes_owner_session_id", "workflow_recipes", ["owner_session_id"]
    )
    op.create_index("ix_workflow_recipes_owner_user_id", "workflow_recipes", ["owner_user_id"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "recipe_id", sa.String(), sa.ForeignKey("workflow_recipes.id"), nullable=False
        ),
        sa.Column(
            "document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=True
        ),
        sa.Column("owner_session_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="completed"),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_runs_recipe_id", "workflow_runs", ["recipe_id"])
    op.create_index("ix_workflow_runs_document_id", "workflow_runs", ["document_id"])
    op.create_index("ix_workflow_runs_owner_session_id", "workflow_runs", ["owner_session_id"])
    op.create_index("ix_workflow_runs_owner_user_id", "workflow_runs", ["owner_user_id"])


def downgrade() -> None:
    op.drop_table("workflow_runs")
    op.drop_table("workflow_recipes")
