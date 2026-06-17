# Railway deployment

There are two supported topologies. **Most deployments should use single-service** (below); the two-service split further down is optional.

## Single-service deploy (recommended, fully automatic)

Deploy **one service** from the repo root. The root [`Dockerfile`](../Dockerfile) bundles the API and the web server into one image; [`scripts/railway-single-service-start.sh`](../scripts/railway-single-service-start.sh) runs DB migrations, starts the API on `127.0.0.1:8000`, and starts the web server on `$PORT`. The web app proxies `/api/*` to the in-container API, so `API_PROXY_TARGET=http://127.0.0.1:8000` is correct — there is no separate API service to point at.

[`railway.json`](../railway.json) at the repo root pins all of this as **config-as-code**, which **always overrides the dashboard**. Every GitHub push redeploys correctly with no manual dashboard changes:

```json
{
  "build":  { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": { "startCommand": "/app/railway-single-service-start.sh", "healthcheckPath": "/api/health" }
}
```

> ⚠️ **Do NOT set a Custom Start Command in the Railway dashboard.** A leftover `pnpm --filter @docos/web start` overrides the Dockerfile and crashes the container with `The executable 'pnpm' could not be found` (the runtime image has no pnpm). `railway.json` now forces the correct start command, so leave the dashboard field empty. If one was set previously, clear it once: **Settings → Deploy → Custom Start Command → Remove**.

Only variable worth setting for real use: an LLM key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). For data that survives redeploys, mount a Railway **volume** at `/app/data` (SQLite DB + local blobs live there).

---

## Two services: API + Web (optional)

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
