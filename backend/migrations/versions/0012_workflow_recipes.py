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


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {
        str(index["name"])
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    # SQLite DDL is non-transactional. A container that is interrupted between
    # CREATE TABLE / CREATE INDEX and Alembic's version stamp leaves a valid
    # object behind while the database still reports 0011. Make the migration
    # replay-safe so the next Railway deployment can finish the upgrade.
    if "workflow_recipes" not in _table_names():
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

    recipe_indexes = _index_names("workflow_recipes")
    if "ix_workflow_recipes_owner_session_id" not in recipe_indexes:
        op.create_index(
            "ix_workflow_recipes_owner_session_id",
            "workflow_recipes",
            ["owner_session_id"],
        )
    if "ix_workflow_recipes_owner_user_id" not in recipe_indexes:
        op.create_index(
            "ix_workflow_recipes_owner_user_id",
            "workflow_recipes",
            ["owner_user_id"],
        )

    if "workflow_runs" not in _table_names():
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "recipe_id",
                sa.String(),
                sa.ForeignKey("workflow_recipes.id"),
                nullable=False,
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

    run_indexes = _index_names("workflow_runs")
    indexes = {
        "ix_workflow_runs_recipe_id": "recipe_id",
        "ix_workflow_runs_document_id": "document_id",
        "ix_workflow_runs_owner_session_id": "owner_session_id",
        "ix_workflow_runs_owner_user_id": "owner_user_id",
    }
    for index_name, column_name in indexes.items():
        if index_name not in run_indexes:
            op.create_index(index_name, "workflow_runs", [column_name])


def downgrade() -> None:
    tables = _table_names()
    if "workflow_runs" in tables:
        op.drop_table("workflow_runs")
    if "workflow_recipes" in tables:
        op.drop_table("workflow_recipes")
