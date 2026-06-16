#!/usr/bin/env sh
# Production entrypoint: apply database migrations, then exec the service command.
# Running migrations here (idempotent) means a fresh deploy self-initialises its schema.
set -e

echo "[entrypoint] applying database migrations…"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
