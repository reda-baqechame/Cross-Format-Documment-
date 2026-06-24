#!/usr/bin/env bash
# Start the API for Playwright E2E (SQLite + local blobs — no Docker required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/docos-e2e.db}"
export LOCAL_BLOB_DIR="${LOCAL_BLOB_DIR:-/tmp/docos-e2e-blobs}"
export SIGNING_SECRET="${SIGNING_SECRET:-playwright-e2e-signing-secret-key}"
export APP_ENV="${APP_ENV:-dev}"
export RATE_LIMIT_ENABLED="${RATE_LIMIT_ENABLED:-0}"

python -m pip install -q -e ".[dev]"
alembic upgrade head
exec uvicorn docos.main:app --host 127.0.0.1 --port 8000
