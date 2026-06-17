# CLAUDE.md — agent & contributor handoff

Read this first, then `docs/implementation-status.md` for **where we left off / what's next**.
This file is the "ramp up and continue precisely" guide.

## What this is

A **trust-grade, cross-format document platform**. One **canonical document model** (a typed
node graph) is the single source of truth: every format parses into it, and every capability
(edit, convert, redact, compare, summarize, sign, page-ops, accessibility…) is implemented
**once, against the model**, so it works across all formats. See `docs/architecture.md` and
`docs/canonical-model.md`.

- Backend: Python 3.11+ / FastAPI / Pydantic v2, managed with **uv**. Code in `backend/src/docos`.
- Frontend: Next.js 14 / React / TS, **pnpm** workspace. Code in `apps/web`.
- Strategy: `docs/competitive-analysis.md`. Build status: `docs/implementation-status.md`.

## Dev workflow (verified commands)

Backend (run from `backend/`):
```bash
uv sync --extra dev --extra anthropic     # install deps (incl. pytest, ruff)
uv run --extra dev python -m pytest -q     # run tests (NOT bare `pytest` — that uses a tool env without deps)
uv run --extra dev ruff check src tests    # lint (CI gate)
uv run --extra dev ruff format <files>     # autofix line-length etc.
```

Frontend (run from repo root):
```bash
pnpm install --frozen-lockfile
pnpm --filter @docos/web exec tsc --noEmit   # typecheck
pnpm --filter @docos/web lint                # eslint (CI gate)
pnpm --filter @docos/web build               # next build (CI gate)
```

CI gates (`.github/workflows/ci.yml`): backend = ruff + pytest; web = tsc + lint + build.
**mypy is not a CI gate** and has pre-existing errors — match surrounding code, don't chase it.

## Core invariants — follow these

1. **Canonical model is the source of truth** (`model/document.py`, `model/nodes.py`). Add
   capabilities over the model, not per-format.
2. **All mutations are reversible patches.** Build a `ReversiblePatch` of `Patch` ops and run it
   through `orchestrator.apply` → `provenance.commit_version` → `provenance.record_event`. The
   op executors live in `services/semantic/orchestrator.py`; the op set is in `model/patch.py`.
3. **Redaction is true removal.** Any reader/exporter that emits node text must go through
   `services/docengine/writers/redaction.py` (`run_text` / `is_redacted`). New features must be
   redaction-aware.
4. **Offline-first / privacy.** Everything must work with `LLM_PROVIDER=noop`. LLM is optional
   enhancement (see `services/semantic/reader.py`): deterministic core, LLM only when configured.
5. **Types don't drift.** Pydantic models in `model/` + `api/schemas.py` define the OpenAPI
   schema; `make codegen` regenerates `packages/shared-types`. Service DTOs live next to the
   service and are imported into `schemas.py` (e.g. `SensitiveFinding`, `Extraction`, `Citation`).

## Recipe: add a new capability (the pattern used throughout)

1. **Service** in `backend/src/docos/services/...` — pure functions over `CanonicalDocument`,
   redaction-aware, deterministic where possible. Define any Pydantic result DTO here.
2. **Schema** — add request/response models in `api/schemas.py`, importing the service DTO.
3. **Route** — add to the relevant `api/routes_*.py` (or a new one) and `include_router` it in
   `main.py`. Mutations: build a `ReversiblePatch` and use apply→commit→audit. Reads: don't commit.
4. **Tests** — a unit test for the service + an integration test through the FastAPI `client`
   fixture (`backend/tests/conftest.py`, SQLite-backed). Cover a redaction/offline case.
5. **Frontend (optional)** — add a client fn in `apps/web/src/lib/api.ts` (all calls go through
   the same-origin `/api` proxy) and surface it in a component.
6. **Track it** — flip the item in `docs/implementation-status.md`.

Reference implementations to copy: `services/provenance/sensitive.py` (+ endpoints in
`routes_patches.py`), `services/semantic/reader.py` (+ `routes_query.py`),
`services/docengine/pageops.py` (+ `routes_pages.py`).

## Where the code lives

```
backend/src/docos/
  model/                 canonical model + reversible patch types
  services/
    docengine/           adapters (parse), writers (export), pageops (PDF ops)
    semantic/            orchestrator (apply patches), reader (Q&A/summarize/translate),
                         extract, classify, llm/ (noop|openai|anthropic)
    provenance/          versioning, audit, health, signing, sensitive, accessibility, diff
    ingestion/           upload validation + scan ; ocr/ ; storage (local|s3)
  api/                   routes_*.py + schemas.py ; main.py mounts routers
apps/web/src/            app/ (pages, /api proxy), components/, lib/api.ts
docs/                    architecture, canonical-model, competitive-analysis, implementation-status
```

## Continuing the work

- The roadmap and live status are in `docs/implementation-status.md` (✅ done · 🟡 partial ·
  ⬜ not started · 🔒 needs external infra). Pick the next ⬜ and follow the recipe above.
- Tractable next: XLSX/PPTX/image export, searchable-PDF generation, multi-document Q&A,
  semantic search.
- 🔒 items (real-time collab, legally-binding PKI e-sign, mobile capture, cloud/IDP
  integrations, ClamAV, TTS) need infrastructure/credentials — their seams exist; wire them
  when that infra is provisioned. Don't fake compliance.
