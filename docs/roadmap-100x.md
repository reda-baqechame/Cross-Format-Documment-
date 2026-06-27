# Roadmap — the "100x" platform

The bottleneck isn't more AI; it's **better document plumbing** plus a **universal editing surface**
users feel in the first 10 seconds. Hosted Claude/OpenAI stay the reasoning layer (already wired via
the `noop|openai|anthropic` seam); around them we add open, **no-strings (MIT/Apache-2.0/BSD/ISC)**
engines for document reality, async scale, and an evaluation lab that proves results.

This file is the staged plan. Items land behind the same **activatable-seam pattern** used across the
app (a settings flag + a `deps.py` factory → the richer engine when installed/configured, else the
built-in default that always works offline). Nothing fakes a capability that needs uninstalled infra.

## Shipped (this lane)

- ✅ **Docling parser seam** (MIT) — `PARSER_ENGINE=docling` routes PDF/DOCX/PPTX/XLSX through Docling
  for richer layout/reading-order/tables; falls back to native adapters when not installed.
  `services/docengine/adapters/docling.py`, gated in `registry.default_registry`.
- ✅ **PaddleOCR seam** (Apache-2.0) — `OCR_ENGINE=paddle` for stronger multilingual OCR; degrades to
  Tesseract when absent. `services/ocr/paddle.py`, `services/ocr/factory.get_ocr_service`.
- ✅ **Apache Tika fallback** (Apache-2.0) — `TIKA_SERVER_URL` sidecar for type-detection / metadata /
  fallback text as a validation layer, never the primary parser. `services/ingestion/tika.py`.
- ✅ **QPDF preflight** (Apache-2.0) — `QPDF_PREFLIGHT=true` repairs/linearizes PDFs before parse when
  the binary is present. `services/ingestion/qpdf.py`.
- ✅ **Async job-status seam** — `GET /jobs/{job_id}` over the `jobs` table so the frontend can poll
  once heavy parse/OCR moves to a worker. `api/routes_jobs.py`.
- ✅ **Document-fidelity eval lab** — deterministic layout/OCR/table/export/redaction metrics + CI gate.
  `evals/document_fidelity/`.

## Next — Universal Workspace (the visible 100x)

- ⬜ **Univer editor** (Apache-2.0) — embed a real spreadsheet/doc/slide editing surface; seed it from
  the canonical model and diff edits back into reversible patch ops (reuse `submitPatch`/`setTableCell`).
  Start with sheets (clean 1:1 with `TableNode`); docs/slides render + light-edit first.
- ⬜ **PDF.js viewer** (Apache-2.0) — page rendering with the existing redaction/annotation overlay.
- ⬜ **Command center first screen** — one dropzone + visible action cards + no-login sample docs, with
  the existing Trust Score and before/after proof front-and-center.
- ⬜ **AI command bar** — promote `AiEditBar` to a persistent palette (`cmdk`, MIT) over `lib/api.ts`.

## Next — async pipeline (scale)

- ⬜ Turn the dormant Celery seam into the real path: `POST /documents?async=true` returns `job_id`
  immediately; a worker does parse/OCR/commit and updates the `jobs` row; frontend polls `GET /jobs`.
  Keep the synchronous path as the default so offline/CI need no Redis. `queue/tasks.ingest_document`.

## Next — AI power layer (depth, not provider count)

- ⬜ Orchestration: intent classifier → retrieve relevant pages/nodes/tables → patch **plan** →
  validate → **dry-run preview** → commit. Today's prompt exposes only 6 ops with a 400-node digest
  (`services/semantic/prompt.py`), though the executor already supports table/image/move ops — widen
  the allowed set toward the executor's real capability.
- ⬜ Specialized chains: contract analyzer, invoice extractor, redaction detector, accessibility fixer,
  format-repair, spreadsheet-formula explainer, comparison agent.
- ⬜ Provider routing: `AI_PRIMARY/FALLBACK/CHEAP/REASONING/VISION_PROVIDER` env model selection
  (settings already supports `llm_model`).

## Next — collaboration & trust polish

- ⬜ Yjs + Hocuspocus (MIT) real-time co-editing over the existing presence seam.
- ⬜ Batch processing, template builder, team workspaces, cloud integrations (seams already exist).
- ⬜ Excalidraw (MIT) diagram mode; Tiptap/Lexical (MIT) semantic rich-text option.

## License discipline (must hold)

Allowed by default: **MIT, Apache-2.0, BSD-2/3, ISC**. Review carefully: MPL, LGPL. **Avoid in the
closed SaaS core:** GPL, AGPL, SSPL, BSL, Commons-Clause, non-commercial/research-only model licenses.

⚠️ **Open license risk to resolve:** the PDF core is **PyMuPDF/fitz (AGPL)**. It is load-bearing today
(`services/docengine/adapters/pdf.py`, page-ops), so it stays for now, but a commercial SaaS should
plan a migration to permissive engines (`pikepdf` — already a dep — `pypdfium2`, `pdf-lib`) and audit
before scaling commercially. Track as a dedicated task; don't rip out under load.
