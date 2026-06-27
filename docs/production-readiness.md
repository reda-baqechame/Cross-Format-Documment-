# Production readiness — what delivers real results, and what needs provisioning

This document is the **honest, verified** map of what the platform actually does. It exists so you can
price and sell with confidence and never over-promise to a paying user. Every "✅ out of the box" item
below was exercised end-to-end against a running instance with the repo's own exhaustive smoke
harnesses; every "needs X" item is a deliberately gated seam that returns a clear, honest response
(not a silent failure) until you configure it.

## How this was verified

Run against a live instance (`scripts/*` target `DOCOS_PRODUCTION_URL`):

```bash
cd backend && uv run python ../scripts/generate-production-fixtures.py
DOCOS_PRODUCTION_URL=<app-url> node scripts/production-tool-matrix.mjs   # every API surface
DOCOS_PRODUCTION_URL=<app-url> node scripts/production-full-test.mjs     # all upload formats
DOCOS_PRODUCTION_URL=<app-url> node scripts/production-client-packet-smoke.mjs
pnpm --filter @docos/web exec node ../../scripts/production-editor-smoke.mjs  # browser editor
```

**Latest run (offline/default config):**
- Tool matrix: **84 passed · 0 failed** · 1 not-applicable · 3 honest gated seams.
- Full format test: **66 passed · 0 failed** · 1 gated (translate).
- Client-packet: **passed** (returned real business warnings).
- Browser editors (Univer sheet + PDF.js reader + word-like editor): covered by the green Playwright
  e2e suite (`apps/web/e2e/*`) and screenshot-verified.

CI on `main` is green across Backend (pytest + stress + 2 eval gates + migrations), Web (tsc + lint +
build + browser e2e), and the read-only production smoke.

## ✅ Works out of the box (offline, zero external services)

These deliver **real results today** with the default config (SQLite, local blobs, `LLM_PROVIDER=noop`):

| Capability | What it does |
|---|---|
| **Upload + parse** | TXT/MD/CSV/HTML/DOCX/PDF/XLSX/PPTX/RTF/PNG/JPG → a real canonical model (magic-byte validated, zip-bomb guarded) |
| **OCR (scans/images)** | Tesseract text recovery with confidence + review flags |
| **Export / convert** | PDF→PDF/DOCX/TXT/HTML/MD/CSV/XLSX/PPTX/PNG/RTF, etc. — files open, with an export-validation report |
| **PDF power-ops** | compress, rotate, watermark, AES-256 protect, merge, split/extract, delete pages, searchable-PDF |
| **True redaction + proof** | redaction is real removal on export; un-redact test proves text is unrecoverable |
| **Metadata sanitize** | strips hidden author/metadata, with before/after proof |
| **Trust / Send-Ready** | document health score + readiness verdict + one-click "clean before send" |
| **Document intelligence** | contract/invoice/receipt/résumé/form typing + actionable checks (totals reconcile, missing clauses) |
| **Key-value extraction** | dates, emails, money, etc. |
| **PII detection → redaction** | high-precision regex (emails/SSN/cards/phones/IPs, phone-validated) → one-click redact |
| **Ask / Summarize / Extract / Classify / Autopilot** | deterministic/extractive results offline (richer with an API key — see below) |
| **Library search + Q&A** | BM25 ranking + multi-document notebook with citations (extractive offline) |
| **Compare / redline** | semantic diff between two documents |
| **Templates / clauses / renewals** | save → instantiate reusable documents; clause library; renewal reminders |
| **Forms** | detect blanks as fields; fill-once profile + autofill |
| **Spreadsheet & PDF editors** | Univer Excel-grade grid (XLSX/CSV) + PDF.js reader; edits are reversible, versioned patches |
| **Integrity-seal e-signature** | tamper-evident HMAC seal + verify (NOT legally binding — see e-sign seam) |
| **Bulk send + recipient portal** | share links, approvals, audit |
| **Versioning + audit** | every change is a reversible patch with a version DAG and event log |

## 🔌 Premium features that need provisioning (honest seams)

Each returns a **clear, honest signal** until configured — `/health` reports its state and the route
returns a `501`/"not connected" message. **Nothing here silently fails or fakes success**, so a user
never pays for something that quietly does nothing.

| Feature | What to set | Result once configured |
|---|---|---|
| **AI: natural-language editing, AI-written answers, richer summaries/analysis** | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (+ optional `LLM_MODEL`) | NL "ask AI to edit/redact/extract", LLM-phrased Q&A. Offline it returns 501 / extractive fallback — honestly. |
| **True off-request async ingest (scale)** | `INGEST_MODE=async`, `CELERY_EAGER=false`, `REDIS_URL`, run `celery -A docos.queue.celery_app worker` | Uploads return a `job_id` instantly; parsing/OCR run on a worker; client polls `GET /jobs/{id}`. (Sync is the default and works without Redis.) |
| **Persistent storage** | `DATABASE_URL` = Postgres; `BLOB_BACKEND=s3` + S3 creds (or keep local) | Durable documents/versions instead of ephemeral SQLite. |
| **Malware scanning** | `SCANNER=clamav` + clamd host/port | Uploads streamed to ClamAV; fails closed if unreachable. |
| **Legally-binding e-signature** | `SIGNATURE_PROVIDER=external` + provider URL/key | Regulated PKI signing. (Default = honest integrity seal, clearly labeled not legally binding.) |
| **Cloud import (Drive/Dropbox/Box/OneDrive/Slack)** | each provider's `*_CLIENT_ID/SECRET` + `OAUTH_REDIRECT_BASE` | Real OAuth import through the same ingest pipeline. |
| **Text-to-speech / DRM** | `TTS_PROVIDER`/`DRM_PROVIDER` = external + URL/key | Audio export / rights-managed export. |
| **Billing** | `STRIPE_SECRET_KEY` + price ids | Checkout. (Returns 501 until set.) |
| **Stronger document intelligence engines** | install + flag: `PARSER_ENGINE=docling`, `OCR_ENGINE=paddle`, `TIKA_SERVER_URL`, `QPDF_PREFLIGHT=true`, `PII_ENGINE=presidio`, `PDF_RENDER_ENGINE=pdfium` | Higher-fidelity layout/tables, multilingual OCR, NER PII, non-AGPL PDF rendering. Each falls back to the built-in default when absent. |

## Recommended production config (unlock the premium tier)

Minimum to make the AI features and scale "real" for paying users:

```bash
# AI (the headline premium value)
ANTHROPIC_API_KEY=sk-ant-...        # or OPENAI_API_KEY
# Durable + scalable
DATABASE_URL=postgresql+psycopg://...    # Postgres, not SQLite
REDIS_URL=redis://...                    # + run a Celery worker
INGEST_MODE=async
CELERY_EAGER=false
# Production hardening
APP_ENV=production
SIGNING_SECRET=<strong-secret>           # not the dev default
SCANNER=clamav                           # if you accept untrusted uploads
BLOB_BACKEND=s3                          # + S3_* creds, or keep local with a persistent volume
```

## The honesty guarantee (why you won't be reimbursing users)

The platform is built to **never claim a capability it can't deliver**:
- `GET /health` returns the true state of every gated capability (`ai_enabled`, `esign_configured`,
  `idp_configured`, `tts_configured`, `cloud_integrations`, `billing_configured`, …) so the UI shows
  "Not connected" instead of pretending.
- Unconfigured features return a `501` with a message saying exactly what to set — not a fake success.
- Redaction is **true removal** (verified unrecoverable), and the integrity seal is explicitly labeled
  "not legally binding" rather than implying regulated e-signature.

So a user only ever sees a feature as available when it genuinely produces results. The premium AI tier
becomes real the moment you set an API key; everything in the "out of the box" table already works.
