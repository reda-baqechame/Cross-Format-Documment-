# Cross-Format Document OS

A **trust-grade cross-format document operating system**: open almost any business document,
preserve layout, understand structure, edit semantically, convert safely, compare versions,
collaborate, redact properly, remove hidden metadata, improve accessibility, and route the final
file into storage or signature systems — without breaking fidelity.

This repository is a **project scaffold**. It establishes the full architecture described in the
opportunity report and ships a thin, runnable vertical slice (upload → canonical model →
model-driven UI + document-health panel) for TXT and DOCX. Every other format and service is a
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
# Web:  http://localhost:3000
make codegen       # regenerate packages/shared-types from the live OpenAPI schema
make test          # backend tests
```

Drag a `.txt` or `.docx` into the web app: it is parsed into the canonical model, rendered on the
canvas, and scored in the document-health panel.

## What works vs. what's stubbed

**Functional day one:** `/health`, upload + ingestion validation, TXT & DOCX parsing into the
canonical model, version + audit persistence, document-health computation, model-driven canvas + panel.

**Stubbed extension points** (importable, raise `NotImplementedError`): PDF/XLSX/PPTX/RTF/image
adapters, real OCR, real LLM semantic editing, S3 blob store, ClamAV scanner, production sandbox,
native e-signature/QES. See [`docs/services/`](docs/services).

## Layout

```
backend/   FastAPI app, canonical model, 5 services, db, queue (see backend/README)
apps/web/  Next.js single-canvas workspace + document-health panel
packages/  shared-types (OpenAPI → TS codegen output)
docs/      architecture, canonical model, privacy modes, ADRs, per-service docs
```

## License

Proprietary — all rights reserved (placeholder; update before distribution).
