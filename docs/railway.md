# Railway deployment

There are two supported topologies. **Most deployments should use single-service** (below); the two-service split further down is optional.

## Single-service deploy (recommended, fully automatic)

Deploy **one service** from the repo root. The root [`Dockerfile`](../Dockerfile) bundles the API and the web server into one image; [`scripts/railway-single-service-start.sh`](../scripts/railway-single-service-start.sh) runs DB migrations, starts the API on `127.0.0.1:8000`, and starts the web server on `$PORT`. The web app proxies `/api/*` to the in-container API, so `API_PROXY_TARGET=http://127.0.0.1:8000` is correct — there is no separate API service to point at.

[`railway.json`](../railway.json) at the repo root pins all of this as **config-as-code**, which **always overrides the dashboard**. Every GitHub push redeploys correctly with no manual dashboard changes:

```json
{
  "build":  { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": { "startCommand": "/app/railway-single-service-start.sh", "healthcheckPath": "/api/ready" }
}
```

**Health endpoints.** The container exposes three:

| Path | Meaning |
|------|---------|
| `/api/live` | Process is up. Never fails while the app can answer — use for liveness only. |
| `/api/ready` | **Deep readiness** — passes only when the DB tables exist, migrations are applied, and blob storage is writable. Railway's healthcheck points here so a broken deploy (e.g. no volume) is **not** marked healthy. |
| `/api/health` | Human-readable status summary (provider, storage, DB) the web UI reads. Always returns 200. |

Because the healthcheck is `/api/ready`, a deploy with no working persistent storage **fails fast** instead of silently losing documents after the next restart.

> ⚠️ **Do NOT set a Custom Start Command in the Railway dashboard.** A leftover `pnpm --filter @docos/web start` overrides the Dockerfile and crashes the container with `The executable 'pnpm' could not be found` (the runtime image has no pnpm). `railway.json` now forces the correct start command, so leave the dashboard field empty. If one was set previously, clear it once: **Settings → Deploy → Custom Start Command → Remove**.

> **Turn on AI features:** In Railway → your service → **Variables**, paste **`ANTHROPIC_API_KEY`** (recommended) or **`OPENAI_API_KEY`**, then click **Redeploy**. No other config is required — the backend auto-selects the provider from whichever key is present (`settings.effective_llm_provider`). After redeploy, open the app → **System status** on the home page; **AI provider** should show as connected. Without a key the app runs fully offline and AI-driven actions (natural-language edit, autopilot, Q&A, translation) use deterministic fallbacks only.

Optional model pin for Anthropic: `LLM_MODEL=claude-sonnet-4-6` (default is `claude-opus-4-8`). `LLM_MODEL` is ignored for OpenAI.

> **Turn on billing (Stripe):** set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and price IDs (`STRIPE_PRICE_PRO`, `STRIPE_PRICE_TEAM`) plus `BILLING_RETURN_URL=https://your-app.up.railway.app/pricing`. Without these, `/pricing` and free-tier features work; portal link creation returns 402 until a Pro subscription is active.

> **Scale beyond SQLite:** for production traffic, switch to managed Postgres + object storage instead of a single volume:
>
> | Variable | Example |
> |----------|---------|
> | `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/docos` |
> | `BLOB_BACKEND=s3` | |
> | `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Or Railway's S3-compatible bucket vars |
>
> Migrations run automatically on boot. Keep the `/app/data` volume as fallback for local blobs when `BLOB_BACKEND` is unset.

> 🛑 **Required for persistence:** mount a Railway **volume** at `/app/data`. The default single-service deploy keeps the SQLite DB at `/app/data/docos.db` and uploaded blobs under `/app/data/blobs`; Railway containers are otherwise ephemeral, so **without the volume every document, version, and upload is lost on the next redeploy or restart** (and, now that the healthcheck is `/api/ready`, the deploy will fail rather than come up broken). For higher-scale production, switch to Postgres + S3-compatible object storage (see the two-service section below) instead of SQLite + local disk.

## Production checklist

**Required**

| Variable | Why |
|----------|-----|
| `APP_ENV=production` | Enables secure cookies + HSTS; **refuses to start** if `SIGNING_SECRET` is still the dev default. |
| `SIGNING_SECRET` | Long random string. Signs the anonymous-session cookie + integrity seals; a forged/weak value breaks document ownership. |
| Volume at `/app/data` (or Postgres `DATABASE_URL` + S3) | Persistence — see the box above. |
| `ANTHROPIC_API_KEY` *or* `OPENAI_API_KEY` | Optional, but AI features are no-ops without it (the app is otherwise fully offline). |

**Optional hardening / ops knobs**

| Variable | Default | Notes |
|----------|---------|-------|
| `CORS_ORIGINS` | `http://localhost:3100` | Only needed for the **two-service** split (the single-service proxy is same-origin, so CORS is unused). Comma-separated allow-list. |
| `LOG_FORMAT` | `human` | Set `json` for structured, aggregatable logs (one JSON object per line, with `request_id`). |
| `SENTRY_DSN` | _(unset)_ | Set to enable error tracking. Requires installing the `[sentry]` extra; **completely inert when unset**. |
| `API_PROXY_TIMEOUT_MS` | `60000` | Web→API upstream timeout (a hung backend yields a clean 504). |
| `RATE_LIMIT_OPS_PER_MIN` | `60` | Per-session+IP **burst** guard on costly ops (AI, export, page ops). Not a daily/total cap. |
| `RATE_LIMIT_UPLOADS_PER_MIN` | `30` | Per-session+IP upload burst guard. |
| `MAX_UPLOAD_MB` | `50` | Streamed upload size cap (413 over the limit). |
| `BLOB_ENCRYPTION=aesgcm` + `BLOB_ENCRYPTION_KEY` | `none` | Opt-in encryption-at-rest for stored blobs. |
| Gated provider seams (e-sign, cloud IDP, handwriting, TTS, DRM, cloud storage, multi-node presence) | _(unset)_ | All off/local by default. See **[docs/providers.md](providers.md)** for the env vars that activate each. |

**First-deploy verification**

1. `GET /api/ready` returns **200** (DB tables present + migrations applied + storage writable). A 503 means the volume/DB isn't working — fix before relying on it.
2. `GET /api/health` shows the expected provider/storage/database (e.g. `database: postgres`, AI provider connected).
3. Upload a file → open it → **export** it back out (round-trips the canonical model + blob storage).
4. Responses carry an `X-Request-ID` header; with `LOG_FORMAT=json`, logs show one correlated line per request.

---

## Two services: API + Web (optional)

Deploy **two Railway services** from this repo. The browser only talks to **Web**; Web proxies `/api/*` to **API** over Railway private networking.

## 1. API service (backend)

| Setting | Value |
|---------|--------|
| Root directory | `backend` |
| Dockerfile | `backend/Dockerfile` |
| Health check path | `/ready` (deep readiness; `/live` for liveness only) |

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
| `DOCOS_RAILWAY_TOPOLOGY` | `split` |

Replace `api` with your **API service name** in Railway.

> ⚠️ **Do not accept Railway's "Suggested Variables" default of `API_PROXY_TARGET=http://localhost:8000`.**
> Inside the Web container `localhost` is the Web service itself, not the API — the site
> will load but every `/api/*` call fails ("Backend not connected"). Always set it to the
> API's private host as shown above. With `DOCOS_RAILWAY_TOPOLOGY=split`, the Web server
> logs a production warning if this is left pointing at localhost.

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
