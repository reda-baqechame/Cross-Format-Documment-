# Railway deployment (two services: API + Web)

Deploy **two Railway services** from this repo. The browser only talks to **Web**; Web proxies `/api/*` to **API** over Railway private networking.

## 1. API service (backend)

| Setting | Value |
|---------|--------|
| Root directory | `backend` |
| Dockerfile | `backend/Dockerfile` |
| Health check path | `/health` |

**Required variables**

| Variable | Example |
|----------|---------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (add Postgres plugin) |
| `SIGNING_SECRET` | long random string |
| `APP_ENV` | `production` |
| `BLOB_BACKEND` | `s3` recommended for production (see below) |
| `LOCAL_BLOB_DIR` | `/app/data/blobs` (only if using `local` + persistent volume) |

### Persistent file storage (required for production)

Railway containers are **ephemeral**. With `BLOB_BACKEND=local`, uploaded files are lost on redeploy and preview/export will break for older documents.

**Recommended:** use S3-compatible storage (AWS S3, Cloudflare R2, MinIO, etc.):

| Variable | Example |
|----------|---------|
| `BLOB_BACKEND` | `s3` |
| `S3_ENDPOINT` | `https://…` (R2/MinIO; omit for AWS) |
| `S3_BUCKET` | `docos-prod` |
| `S3_ACCESS_KEY` | … |
| `S3_SECRET_KEY` | … |
| `S3_REGION` | `auto` or AWS region |

**Alternative:** mount a Railway **volume** at `/app/data/blobs`, keep `BLOB_BACKEND=local`, and set `LOCAL_BLOB_DIR=/app/data/blobs`.

**Optional**

| Variable | Notes |
|----------|--------|
| `PORT` | Set automatically by Railway |
| `LLM_PROVIDER` | `noop` (default, offline) |
| `PRIVACY_MODE` | `offline` |

Migrations run automatically on container start (`docker-entrypoint.sh`).

## 2. Web service (frontend)

| Setting | Value |
|---------|--------|
| Root directory | `/` (repo root) |
| Dockerfile | `apps/web/Dockerfile` |
| Build | Docker (see Dockerfile — needs monorepo context) |

**Required variables**

| Variable | Value |
|----------|--------|
| `API_PROXY_TARGET` | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}` |

Replace `api` with your **API service name** in Railway.

> ⚠️ **Do not accept Railway's "Suggested Variables" default of `API_PROXY_TARGET=http://localhost:8000`.**
> Inside the Web container `localhost` is the Web service itself, not the API — the site
> will load but every `/api/*` call fails ("Backend not connected"). Always set it to the
> API's private host as shown above. (In production the Web server logs a warning if this
> is left pointing at localhost.)

**Alternative** (if you prefer split vars):

| Variable | Value |
|----------|--------|
| `API_RAILWAY_PRIVATE_DOMAIN` | `${{api.RAILWAY_PRIVATE_DOMAIN}}` |
| `API_PORT` | `${{api.PORT}}` |

`PORT` is set automatically by Railway for the web container.

## 3. Verify from your phone

1. Open your **Web** public URL (e.g. `https://your-app.up.railway.app`).
2. You should **not** see “Backend not connected”.
3. Upload a PDF or Word file — it should open on the document page.
4. If upload fails, check Web service logs for `proxy: backend unreachable`.

## Common mistakes

- **Only one service deployed** — Web needs the API service running.
- **`API_PROXY_TARGET` missing or `localhost`** — inside Railway, `localhost` is not the API.
- **API service name mismatch** — reference must match the service slug in Railway.
- **No Postgres / `DATABASE_URL`** — uploads fail with 500 on persist.
- **Local blobs without a volume** — uploads work until the next deploy, then previews fail.

## Single-domain note

CORS is not required for the browser: all API calls go through the Web app’s `/api/*` proxy on the same origin.
