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

# ── Make the data dirs exist and be writable ─────────────────────────────────
# A Railway volume mounted at /app/data lands as root-owned, so a non-root runtime
# user can't write to it (SQLite then fails with "unable to open database file").
# If we're root, fix ownership; if we can't write, fail loudly with the reason.
DATA_ROOT="/app/data"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_ROOT"
  chown -R app:app "$DATA_ROOT" 2>/dev/null || true
fi
mkdir -p "$DATA_ROOT" "$LOCAL_BLOB_DIR"

# For a SQLite DATABASE_URL, ensure the database file's directory exists.
case "$DATABASE_URL" in
  sqlite:*//*)
    db_path="$(printf '%s' "$DATABASE_URL" | sed -e 's/^sqlite[^/]*:\/\///' -e 's/^\///')"
    db_dir="$(printf '/%s' "$(dirname "$db_path")" | sed 's#//*#/#g')"
    mkdir -p "$db_dir" || true
    ;;
esac

if ! ( : > "$DATA_ROOT/.write-test" ) 2>/dev/null; then
  echo "[railway] FATAL: $DATA_ROOT is not writable by uid $(id -u)."
  echo "[railway]   If you mounted a volume there, redeploy after this image (it self-heals"
  echo "[railway]   when running as root), or remove the volume to use ephemeral storage."
  exit 1
fi
rm -f "$DATA_ROOT/.write-test" 2>/dev/null || true

echo "[railway] uid=$(id -u) PORT=${PORT} API_PORT=${API_PORT}"
echo "[railway] API_PROXY_TARGET=${API_PROXY_TARGET}"
echo "[railway] BLOB_BACKEND=${BLOB_BACKEND} LOCAL_BLOB_DIR=${LOCAL_BLOB_DIR}"
echo "[railway] applying database migrations"

cd /app/backend
if ! alembic upgrade head; then
  echo "[railway] FATAL: database migration failed (see error above)."
  exit 1
fi

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
    set +e
    wait "$api_pid"
    status=$?
    echo "[railway] FATAL: API process exited with status ${status} (137=OOM-killed)."
    exit 1
  fi

  if ! kill -0 "$web_pid" 2>/dev/null; then
    set +e
    wait "$web_pid"
    status=$?
    echo "[railway] FATAL: web process exited with status ${status} (137=OOM-killed)."
    # Always non-zero so Railway's restart policy retries instead of leaving us down.
    exit 1
  fi

  sleep 5
done
