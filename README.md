# Cross-Format Document OS

A **trust-grade cross-format document operating system**: open almost any business document,
preserve layout, understand structure, edit semantically, convert safely, compare versions,
collaborate, redact properly, remove hidden metadata, improve accessibility, and route the final
file into storage or signature systems — without breaking fidelity.

This repository is a **project scaffold**. It establishes the full architecture described in the
opportunity report and ships a thin, runnable vertical slice (upload → canonical model →
model-driven UI + document-health panel) for TXT, DOCX and PDF. Every other format and service is a
clearly marked, pluggable extension point.

## Why this exists

The document market is fragmented by file type and by trust requirement: native suites own
authoring, PDF tools own manipulation, and agreement platforms own signing — but no single product
combines high-fidelity cross-format editing, structure-preserving semantic AI, trust controls
(redaction/metadata/accessibility), and privacy-first deployment. This project targets that white
space. See [`docs/architecture.md`](docs/architecture.md).

## Architecture at a glance

Five backend services sit around one **canonical document model** (a typed node graph that is the
single source of truth). Edits are applied as **reversible patches**, never free-form regeneration.

| Service | Responsibility |
|---|---|
| Ingestion & safety gateway | File-type allow-list, magic-byte sniff, malware scan, sandboxed staging |
| Document engine | Per-format adapters: parse → canonical model, render preview, export |
| OCR & structure | Scan cleanup, recognition, table extraction, reading-order inference |
| Semantic orchestration | Intent → reversible patch (provider-agnostic LLM client; offline noop default) |
| Provenance & policy | Versioning, audit log, labels, redaction state, accessibility & signature health |

```
┌──────────┐   upload   ┌────────────┐  CanonicalDocument  ┌──────────────┐
│ Frontend │ ─────────► │ Ingestion  │ ──────────────────► │  Document     │
│ (Next.js)│            │ gateway    │                     │  engine       │
│ canvas   │ ◄───────── │            │ ◄────────────────── │  (adapters)   │
│ renders  │  model +   └────────────┘                     └──────────────┘
│ from the │  health           │  records versions/audit/health │
│ model    │            ┌──────▼─────────┐         ┌─────────────▼────────┐
└──────────┘            │ Provenance &   │         │ Semantic (patches)   │
                        │ policy         │         │  + OCR (structure)   │
                        └────────────────┘         └──────────────────────┘
```

## Stack

- **Frontend:** Next.js 14 (App Router) + React 18 + TypeScript, Tailwind, Zustand, TanStack Query.
  The canvas renders **from the canonical model**, not the raw file.
- **Backend:** Python 3.12 + FastAPI + Pydantic v2. Pydantic models *are* the canonical model and
  drive OpenAPI → TypeScript codegen, so types never drift.
- **Document libs:** PyMuPDF, python-docx, openpyxl, python-pptx, striprtf, Pillow, pytesseract,
  pikepdf — one pluggable adapter per format.
- **Data/infra:** PostgreSQL + SQLAlchemy + Alembic, Redis + Celery, a `BlobStore` abstraction
  (local default; S3/MinIO for enterprise/cloud).

## Quickstart

```bash
cp .env.example .env
make up            # postgres, redis, minio, api, worker, web
make migrate       # apply database schema
# API:  http://localhost:8000  (docs at /docs)
# Web:  http://localhost:3100
make codegen       # regenerate packages/shared-types from the live OpenAPI schema
make test          # backend tests
```

Drag any supported file into the web app: it is parsed into the canonical model, rendered on the
canvas, editable, and scored in the document-health panel.

## Production deployment

See **[docs/railway.md](docs/railway.md)** for Railway. The recommended deploy is now a
single service from the repo root: one container starts the API on `127.0.0.1:8000` and the web
server on Railway's `$PORT`, with `/api/*` proxied internally.

```bash
cp .env.example .env          # set APP_ENV=production, SIGNING_SECRET, POSTGRES_PASSWORD,
                              # S3 creds, and API_PROXY_TARGET if you split web/API services
make prod-up                  # builds prod images; the API runs `alembic upgrade head` on start
make prod-down
```

`docker-compose.prod.yml` builds the hardened backend image (non-root, Tesseract, uvicorn workers,
migrate-on-start) and the Next.js **standalone** web image, backed by Postgres, Redis and MinIO.
The API **refuses to start** in `staging`/`production` if `SIGNING_SECRET` is left at its dev
default.

**Topology:** the browser only talks to the web app, which proxies `/api/*` to the backend
server-side (`app/api/[...path]/route.ts`). In the recommended single-service Railway deploy, the
web server reaches the in-container API at `http://127.0.0.1:8000`. In the optional two-service
split, set `API_PROXY_TARGET` on the web service to the API service's private Railway URL, e.g.
`http://<backend-service>.railway.internal:8000`. CI (`.github/workflows/ci.yml`) runs ruff + pytest, verifies migrations apply with no
drift, and typechecks/builds the web app on every push.

## Capabilities

**Open** TXT, DOCX, PDF, XLSX, PPTX, RTF, and images (best-effort OCR when Tesseract has language
data) into one canonical model. **Edit** inline, via explicit deterministic ops, or with AI
natural-language instructions (LLM tool-use → validated patch ops; deterministic no-op offline).
**Save** every change as a versioned, audited, reversible patch — with one-click undo, plus a
rich-formatting toolbar (bold/italic/underline) that rides the same patch pipeline. **Download**
from any source format as DOCX, XLSX, PPTX, PNG, Markdown, HTML, CSV or TXT — or as a **PDF with
edits and redactions burned in**.
**Review** with comment threads anchored to any node (reply / resolve, versioned like every edit).
**Ask** a single question across your whole library — the multi-document notebook answers with
citations that link back to the source document — and **find** documents by relevance with semantic
(TF-IDF) search, all offline. **Trust**: metadata sanitization, true redaction on export,
tamper-evident e-signature, and the document-health panel. **Infra**: local or S3 blob storage,
document CRUD, Alembic migrations.

Remaining extension points: faithful PDF text reflow/font-matching (edits are written back in
place today), and the ClamAV scanner / production microVM sandbox seams. See
[`docs/services/`](docs/services).

## Layout

```
backend/   FastAPI app, canonical model, 5 services, db, queue (see backend/README)
apps/web/  Next.js single-canvas workspace + document-health panel
packages/  shared-types (OpenAPI → TS codegen output)
docs/      architecture, canonical model, privacy modes, ADRs, per-service docs
```

## License

Proprietary — all rights reserved (placeholder; update before distribution).
