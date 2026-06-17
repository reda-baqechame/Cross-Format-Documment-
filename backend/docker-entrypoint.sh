#!/usr/bin/env sh
# Production entrypoint: apply database migrations, then start the service command.
set -e

echo "[entrypoint] applying database migrations…"
alembic upgrade head

if [ $# -gt 0 ]; then
  echo "[entrypoint] starting: $*"
  exec "$@"
fi

PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-4}"
echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT} (${WORKERS} workers)"
exec uvicorn docos.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS"
