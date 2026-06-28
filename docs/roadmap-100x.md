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
- ✅ **Async ingest pipeline** — `INGEST_MODE=async` stages the upload, returns a `job_id`, and parses
  off the request path; the client polls `GET /jobs/{job_id}` (`resolveUploadDocId` in `lib/api.ts`).
  The shared `persist_document` core runs identically inline (eager) or on a Celery worker. Sync stays
  the default so offline/CI need no Redis. `api/routes_documents.py`, `queue/tasks.py`, `api/routes_jobs.py`.
  Run a real worker with: `celery -A docos.queue.celery_app worker` (set `INGEST_MODE=async`,
  `CELERY_EAGER=false`).
- ✅ **Document-fidelity eval lab** — deterministic layout/OCR/table/export/redaction metrics + CI gate.
  `evals/document_fidelity/`.
- ✅ **pypdfium2 permissive render seam** (Apache-2.0/BSD-3) — `PDF_RENDER_ENGINE=pdfium` rasterizes PDF
  pages with the non-AGPL PDFium engine (migration step 1 off PyMuPDF); falls back to PyMuPDF when not
  importable. Rendering only — parsing still PyMuPDF. `services/docengine/pdfium.py`.
- ✅ **PdfEngine boundary + permissive page ops/encryption/compress** — `PDF_ENGINE=permissive` routes
  merge/split/reorder/rotate/delete/encrypt(AES-256 R6)/compress through **pypdf + pikepdf**
  (parity-proven against PyMuPDF in `tests/test_pdfengine_parity.py`), removing the AGPL dependency
  from those code paths. Watermark/text-extraction/redaction/searchable-PDF still fall back to
  PyMuPDF until fidelity parity and are honestly flagged in `/api/capabilities`. Migration step 2.
  `services/docengine/pdfengine/`, `services/docengine/pageops.py` (now a façade over the boundary).
- ✅ **Capabilities truth ledger** — `GET /api/capabilities` exposes each capability's real state
  (`verified | degraded | provider_gated | disabled | broken | claim_without_proof`), the active
  engine + version, limitations, proof_id (citing the production-matrix outcome), and the AGPL licence
  risk. UI controls and marketing must derive from this rather than asserting availability.
  `api/routes_capabilities.py`, `services/engines/`.
- ✅ **Near-duplicate detection** (rapidfuzz, MIT) — `GET /documents/duplicates` clusters duplicate
  invoices/contracts/re-uploads by text similarity. `services/provenance/duplicates.py`.
- ✅ **Phone-PII validation** (phonenumbers, Apache-2.0) — validates phone candidates before flagging,
  cutting false positives in the redaction scanner. `services/provenance/sensitive.py`.
- ✅ **Presidio PII seam** (MIT) — `PII_ENGINE=presidio` augments the regex detector with NER entities
  (names, locations, dates, …) for "redact all personal information"; merges without double-counting and
  falls back to regex-only when not installed. `services/provenance/presidio.py` + `pii.py`. Install with
  `pip install presidio-analyzer` + a spaCy model (e.g. `python -m spacy download en_core_web_lg`).

## Universal Workspace (the visible 100x)

- ✅ **Univer Sheets editor** (Apache-2.0) — XLSX/CSV documents open in a real Excel-grade grid (ribbon,
  formula bar, 450+ functions, sort/filter) seeded from the canonical `TableNode`s; cell edits commit
  through the existing `setTableCell` reversible-patch path. Lazy-loaded client-only (`ssr:false`); the
  plain `SheetEditor` stays as a "Simple" fallback. Verified rendering in a real browser (Chromium).
  `components/canvas/UniverSheet.tsx`, e2e `apps/web/e2e/universal-workspace.spec.ts`.
- ✅ **PDF.js reader** (Apache-2.0) — a crisp client-side vector PDF view with a selectable text layer,
  toggled **Read/Edit** against the existing editable raster+overlay; fed the redaction-applied bytes
  (`?format=pdf`). Pinned to pdfjs v4 (v6 needs `Map.getOrInsertComputed`, unavailable in many
  browsers); worker served from `/public`. Browser-verified. `components/canvas/PdfReader.tsx`.
- ⬜ **Univer Docs/Slides** for DOCX/PPTX (render + light-edit; structural ops via `ModifyStudio`).
- ⬜ **Command center first screen** — one dropzone + visible action cards + no-login sample docs, with
  the existing Trust Score and before/after proof front-and-center.
- ⬜ **AI command bar** — promote `AiEditBar` to a persistent palette (`cmdk`, MIT) over `lib/api.ts`.

## AI power layer (depth, not provider count)

- ✅ **Retrieval + plan + dry-run preview** — large documents now narrow the model's digest to the
  BM25-relevant nodes for the instruction (`services/semantic/retrieval.py`, pure-Python, no deps)
  instead of the first N. A new `POST /documents/{id}/patches/plan` returns a validated, **non-committed**
  before/after preview (`services/semantic/preview.py`); the UI shows it and applies only on approval
  (`AiEditBar` Preview → Apply). Allowed ops widened with `set_table_cell` (pairs with the sheet editor).
- ⬜ Widen the allowed-op set further toward the executor's real capability (table rows/cols, image,
  move) — `services/semantic/prompt.py` `_ALLOWED_OPS` + `_coerce_op`.
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

⚠️ **Open license risk (migration in progress):** the PDF core is **PyMuPDF/fitz (AGPL)**.
**Step 1 done** — page *rendering* can now run on permissive **pypdfium2** (`PDF_RENDER_ENGINE=pdfium`).
**Step 2 done** — *page operations* (merge/split/reorder/rotate/delete), *encryption* (AES-256 R6), and
*compress* now run on permissive **pypdf + pikepdf** (`PDF_ENGINE=permissive`), parity-proven in
`tests/test_pdfengine_parity.py`. Still on PyMuPDF: PDF **parsing** (`adapters/pdf.py` text/table
extraction), **redaction write-back**, and **searchable-PDF** writing — these have no clean permissive
drop-in yet and are honestly flagged in `/api/capabilities`. Remaining migration: move parsing to
`pypdfium2`/`pdfplumber`, redaction to a dedicated path, then drop the `pymupdf` dependency. Until then
PyMuPDF stays load-bearing for those capabilities; don't rip it out under load.
