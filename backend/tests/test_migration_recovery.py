from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_upgrade_recovers_partially_applied_sqlite_migrations(tmp_path: Path) -> None:
    database_path = tmp_path / "partial-migration.db"
    database_url = f"sqlite:///{database_path.resolve().as_posix()}"
    _run_alembic(database_url, "upgrade", "0011")

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE workflow_recipes (
                id VARCHAR NOT NULL PRIMARY KEY,
                owner_session_id VARCHAR,
                owner_user_id VARCHAR,
                name VARCHAR NOT NULL,
                trigger VARCHAR DEFAULT 'manual' NOT NULL,
                steps JSON NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE INDEX ix_workflow_recipes_owner_session_id
                ON workflow_recipes (owner_session_id);
            ALTER TABLE document_shares ADD COLUMN token_ciphertext TEXT;
            """
        )

    _run_alembic(database_url, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        recipe_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list('workflow_recipes')")
        }
        run_indexes = {row[1] for row in connection.execute("PRAGMA index_list('workflow_runs')")}
        share_columns = {
            row[1] for row in connection.execute("PRAGMA table_info('document_shares')")
        }

    assert revision == ("0014",)
    assert {"workflow_recipes", "workflow_runs"} <= tables
    assert {
        "ix_workflow_recipes_owner_session_id",
        "ix_workflow_recipes_owner_user_id",
    } <= recipe_indexes
    assert {
        "ix_workflow_runs_recipe_id",
        "ix_workflow_runs_document_id",
        "ix_workflow_runs_owner_session_id",
        "ix_workflow_runs_owner_user_id",
    } <= run_indexes
    assert "token_ciphertext" in share_columns
    # Migration 0014 added the expert packet-audit tables; they must exist after head.
    assert {"packets", "packet_documents", "packet_audit_runs"} <= tables

    _run_alembic(database_url, "downgrade", "0011")
    _run_alembic(database_url, "upgrade", "head")
