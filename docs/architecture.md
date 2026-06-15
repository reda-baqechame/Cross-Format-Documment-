# Architecture

Cross-Format Document OS is built around a single idea: **one canonical document
model is the source of truth**, and everything else is a service that reads from or
writes to it. This is what lets the product be cross-format without re-implementing
every feature per file type.

## The five services

```
              ┌─────────────────────────────────────────────┐
   upload ───►│ 1. Ingestion & safety gateway                │
              │    allow-list · magic bytes · scan · stage    │
              └───────────────┬─────────────────────────────┘
                              │ bytes + mime
              ┌───────────────▼─────────────────────────────┐
              │ 2. Document engine (FormatAdapter registry)  │
              │    parse → CanonicalDocument → export        │◄── 3. OCR & structure
              └───────────────┬─────────────────────────────┘     (scans → nodes)
                              │ CanonicalDocument
        ┌─────────────────────┼─────────────────────────────┐
        ▼                     ▼                              ▼
┌───────────────┐   ┌──────────────────┐         ┌────────────────────────┐
│ 5. Provenance │   │ 4. Semantic       │         │  Frontend canvas         │
│  & policy      │   │  orchestration    │         │  renders FROM the model  │
│  versions ·    │   │  intent → patch   │         │  + document-health panel │
│  audit ·       │   │  apply / revert   │         └────────────────────────┘
│  health        │   └──────────────────┘
└───────────────┘
```

1. **Ingestion & safety gateway** (`services/ingestion`) — the only entry for
   external bytes. Allow-lists MIME types, sniffs magic bytes, scans for malware, and
   stages bytes into the blob store. Upload is the first security boundary (OWASP).
2. **Document engine** (`services/docengine`) — a registry of `FormatAdapter`s. Each
   adapter is the only code that understands a format's binary details and maps it both
   ways against the canonical model. TXT and DOCX are functional; others are stubs.
3. **OCR & structure** (`services/ocr`) — recovers text, tables, and reading order from
   scans/images. Low-confidence output is meant to be reviewed, never silently trusted.
4. **Semantic orchestration** (`services/semantic`) — turns a natural-language
   instruction into a **reversible patch** over the node graph, then applies/reverts it.
   It depends only on the `LLMClient` interface, so providers (and the offline noop) are
   swappable. It never regenerates whole files.
5. **Provenance & policy** (`services/provenance`) — versions every change as a
   content-hashed snapshot, writes an append-only audit log, applies labels, and computes
   the **document-health** DTO (accessibility, metadata risk, redaction, signature).

## Why a canonical model

PDFs, DOCX, scans, and spreadsheets represent content completely differently. Editing
each format in its own silo is why today's tools fragment. By parsing every format into
one typed node graph (`model/`), every capability — editing, diffing, redaction,
accessibility, health — is implemented once, against the model.

See [`canonical-model.md`](canonical-model.md) for the node taxonomy and
[`privacy-modes.md`](privacy-modes.md) for how config swaps implementations.

## Data flow on upload (the functional vertical slice)

1. `POST /documents` → gateway validates + scans + stages.
2. The adapter registry resolves the MIME to an adapter and `parse()`s bytes into a
   `CanonicalDocument`.
3. Provenance commits the initial version (id = canonical content hash) and writes an
   audit event.
4. `GET /documents/{id}/model` returns the model; the frontend canvas renders from it.
5. `GET /documents/{id}/health` returns the health DTO for the panel.

## Type safety across the stack

The Pydantic models in `backend/src/docos/model` and `api/schemas.py` define the OpenAPI
schema. `make codegen` turns that schema into `packages/shared-types/src/generated.ts`,
so the frontend and backend never drift. A hand-written baseline lives in
`packages/shared-types/src/index.ts`.
