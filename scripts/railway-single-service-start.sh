#!/usr/bin/env sh
# Run the API and web server in one Railway container.
set -eu

PORT="${PORT:-3000}"
API_PORT="${API_PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"

export PORT
export API_PORT
export API_PROXY_TARGET="${API_PROXY_TARGET:-http://127.0.0.1:${API_PORT}}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////app/data/docos.db}"
export BLOB_BACKEND="${BLOB_BACKEND:-local}"
export LOCAL_BLOB_DIR="${LOCAL_BLOB_DIR:-/app/data/blobs}"

mkdir -p "$LOCAL_BLOB_DIR"

echo "[railway] API_PROXY_TARGET=${API_PROXY_TARGET}"
echo "[railway] DATABASE_URL is configured"
echo "[railway] applying database migrations"

cd /app/backend
alembic upgrade head

echo "[railway] starting API on 127.0.0.1:${API_PORT}"
uvicorn docos.main:app --host 127.0.0.1 --port "$API_PORT" --workers "$WEB_CONCURRENCY" &
api_pid="$!"

echo "[railway] starting web on 0.0.0.0:${PORT}"
cd /app/web
node apps/web/server.js &
web_pid="$!"

cleanup() {
  kill "$api_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

while true; do
  if ! kill -0 "$api_pid" 2>/dev/null; then
    echo "[railway] API process exited"
    exit 1
  fi

  if ! kill -0 "$web_pid" 2>/dev/null; then
    echo "[railway] web process exited"
    wait "$web_pid" || exit "$?"
    exit 0
  fi

  sleep 5
done
