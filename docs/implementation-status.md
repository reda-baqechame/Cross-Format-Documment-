# Implementation Status — the "everything people do with documents" superset

Tracks every capability from [`competitive-analysis.md`](competitive-analysis.md) §4 against
what is actually built. Legend: ✅ done · 🟡 partial · 🔜 in progress · ⬜ not started ·
🔒 needs external infra/services (scaffolded or deferred, with reason).

This file is the source of truth for "don't forget anything." Update it as features land.

> **The "100x" lane** (Universal Workspace editor, async pipeline, deeper AI orchestration) is
> tracked in [`roadmap-100x.md`](roadmap-100x.md). Activatable document-intelligence engines that
> have already landed are listed under **§B** below.

## A. Capture & ingest
- ✅ Upload TXT/DOCX/PDF/XLSX/PPTX/RTF/MD/CSV/HTML/image (magic-byte validated, OOXML verified by package
  contents not extension, zip-bomb limits) — `services/ingestion`
- ✅ First-class Markdown / CSV / HTML import adapters — `services/docengine/adapters`
- ✅ Bulk/multi-file import (drag many files; per-file result) — `components/upload/UploadDropzone`
- ✅ OCR structure extraction — `TesseractOcr` recognises positioned, confidence-scored word runs
  (`image_to_data` → `RunNode` + bbox + `attrs.confidence`/`ocr_review`), geometric reading order,
  Pillow cleanup; the image adapter prefers a confident scanned-grid table, then structured OCR,
  then flat text. **Conservative scanned-grid tables** (`build_table_nodes`): a `TableNode` subtree
  is emitted only on a clear full-page grid (≥2 rows × ≥2 aligned columns, every column across ≥2
  rows, ≥70% of words participating) so prose is never mangled. — `services/ocr/tesseract.py`,
  `adapters/image.py`
- ✅ Mobile camera capture — installable PWA (`public/manifest.webmanifest`) + a "Scan with camera"
  affordance (`accept=image/* capture=environment`) on the dropzone; a phone shoots a doc straight
  into the ingest pipeline. Native apps still 🔒. — `components/upload/UploadDropzone.tsx`
- 🟡 Import from Drive/Dropbox/Box/OneDrive/Slack — **OAuth seam wired** (`services/integrations`,
  `routes_integrations.py`): real authorization-code handshake + token store + token-authenticated
  import through the shared ingest pipeline. Activate per provider with `<PROVIDER>_CLIENT_ID/SECRET`
  + `OAUTH_REDIRECT_BASE`; inert/not-connected without creds.
- 🔒 ODT / EPUB / XML / JSON / Google Docs / Sheets / Slides imports — future adapters or OAuth integrations
- 🟡 Handwriting OCR — **seam wired** (`services/ocr/handwriting.py`): calls a specialized model
  when `HANDWRITING_PROVIDER_URL` is set; otherwise standard OCR (honest "not connected").

## B. Understand it (OCR, IDP, structure)
- ✅ **Activatable document-intelligence engines** (no-strings, default-off seams):
  - ✅ **Docling** parser (MIT) — `PARSER_ENGINE=docling` for richer PDF/DOCX/PPTX/XLSX layout +
    reading order + real table structure; transparent fallback to native adapters when not installed.
    — `services/docengine/adapters/docling.py`, `registry.default_registry`
  - ✅ **PaddleOCR** (Apache-2.0) — `OCR_ENGINE=paddle` for stronger multilingual OCR; degrades to
    Tesseract when absent. — `services/ocr/paddle.py`, `services/ocr/factory.py`
  - ✅ **Multi-engine OCR consensus** — `OCR_ENGINE=consensus` runs every available engine and keeps
    the highest-mean-confidence result (best-engine routing); equals Tesseract when alone.
    — `services/ocr/consensus.py`
  - ✅ **Source-engine + confidence provenance** on every OCR run (`attrs.source_engine`/`confidence`),
    surfaced by the HITL review queue. — `services/ocr/tesseract.py`, `services/ocr/paddle.py`
- ✅ **HITL review queue** — `GET /documents/{id}/review-items` lists low-confidence OCR words +
  low-confidence typed fields (redaction-aware); correct via the existing patch endpoint.
  — `services/semantic/review.py`
  - ✅ **Apache Tika** (Apache-2.0) — `TIKA_SERVER_URL` sidecar for detection / metadata / fallback
    text as a validation layer (never the primary parser). — `services/ingestion/tika.py`
  - ✅ **QPDF** preflight (Apache-2.0) — `QPDF_PREFLIGHT=true` repairs/linearizes PDFs before parse
    when the binary is present. — `services/ingestion/qpdf.py`
  - ✅ **Document-fidelity eval lab** — deterministic layout/OCR/table/export/redaction metrics +
    CI gate. — `evals/document_fidelity/`
  - ✅ **Univer spreadsheet editor** (Apache-2.0) — XLSX/CSV open in a real Excel-grade grid (ribbon,
    formula bar, 450+ functions) seeded from `TableNode`s; edits commit via `setTableCell`. Browser-
    verified. — `apps/web/src/components/canvas/UniverSheet.tsx`
  - ✅ **PDF.js reader** (Apache-2.0) — crisp vector PDF view + selectable text layer, Read/Edit toggle
    against the editable overlay, redaction-applied bytes. Browser-verified. — `components/canvas/PdfReader.tsx`
  - ✅ **Library search upgraded to BM25** — `corpus.semantic_search` ranks with BM25 (shared
    `retrieval.bm25_scores`) for better relevance. — `services/semantic/corpus.py`
  - ✅ **Async ingest pipeline** — `INGEST_MODE=async` returns a `job_id` and parses off the request
    path (shared `persist_document` core runs inline when eager, or on a Celery worker); client polls
    `GET /jobs/{job_id}`. Sync stays the default (no Redis needed offline). — `api/routes_documents.py`,
    `queue/tasks.py`, `api/routes_jobs.py`
- ✅ **AI orchestration: retrieve → plan → dry-run preview → commit** — BM25 relevance retrieval picks
  the nodes the model sees on large docs (`services/semantic/retrieval.py`); `POST /documents/{id}/patches/plan`
  returns a validated, non-committed before/after preview (`services/semantic/preview.py`) the UI approves
  before applying (`AiEditBar`). `set_table_cell` added to the AI op set. — `api/routes_patches.py`
- ✅ **Document synthesis (deliverables, not just findings)** — generate a NEW document (exception
  report / AP reconciliation / customs summary) from a pack's findings, downloadable as
  PDF/XLSX/DOCX/HTML/MD via the existing writers. — `services/synthesis/report_builder.py`,
  `POST /packs/{pack}/report?format=…`
- ✅ **End-to-end DocumentOps run** — `POST /documentops/run` orchestrates classify → pack-compare →
  synthesize → queryable audit trail (`GET /documentops/runs/{id}`); read-only, mutations stay
  approval-gated. Killer demo: `evals/demo_import_export`. — `services/workflows/runner.py`,
  `api/routes_documentops.py`
- ✅ **Pack-extraction accuracy gate** — finance/import-export field + finding correctness measured
  in CI. — `evals/pack_extraction`
- ✅ Parse to structured model (nodes, reading order, tables)
- ✅ Table extraction — PDF tables detected via PyMuPDF `find_tables()` → `TableNode`/`TableRow`/
  `TableCell` in the canonical model (dedup vs text blocks, reading-order preserved), exported by
  the existing xlsx writer — `services/docengine/adapters/pdf.py`
- ✅ Key-value / entity extraction (dates, emails, money, etc.) — `services/semantic/extract.py`
- ✅ Document classification — `services/semantic/classify.py`
- ✅ Typed document intelligence (invoice/receipt/contract/résumé/**forms + templates**/**presentation + visual docs**):
  per-kind fields **plus actionable checks** — invoice totals reconcile, contract clause gaps +
  risky language, résumé ATS/contact gaps, subtype-specific form checks (application,
  registration, contact, order, feedback, survey, consent, intake, booking, evaluation,
  inspection, checklist, timesheet, expense, incident, request, approval) and visual-document
  checks (pitch/sales/training/webinar decks, infographic, poster, flyer, brochure,
  one-page summary, dashboard, flowchart, mind map, org chart, diagram, roadmap, timeline);
  redaction-aware, offline —
  `services/semantic/intelligence/`, `GET /documents/{id}/intelligence`,
  `components/canvas/IntelligencePanel`. Home "Analyze & validate" tile + library type badges.
- ✅ **Document Skills + Autopilot** — recognizes the ~15-category document-purpose taxonomy,
  extracts typed fields per purpose with confidence, runs checks (e.g. invoice totals), flags
  what needs human review, and recommends next actions. Deep skills: invoice, contract, résumé,
  proposals/SOWs, reports, SOPs/manuals, marketing/sales, financial, legal, technical,
  research/education, import-export/shipping, and real-estate documents; generic fallback for
  every other recognized type. `GET /documents/{id}/autopilot` +
  Autopilot workspace tab — `services/semantic/skills/`
- ✅ Searchable-PDF generation (invisible OCR layer for scans; born-digital text otherwise) — `writers/searchable_pdf.py`
- 🟡 Cloud IDP (Textract/ABBYY/Google) parity — **seam wired** (`services/ocr/idp.py`,
  `GET /documents/{id}/idp-extract`): uses AWS Textract (boto3) or a custom IDP endpoint when
  configured, else falls back to the deterministic local extractor. Activate with `IDP_PROVIDER=textract`
  (+ AWS creds) or `IDP_PROVIDER=external` + `IDP_PROVIDER_URL`.

## C. Edit & author
- ✅ Inline text edit · ✅ explicit structural ops · ✅ AI natural-language edit (validated)
- ✅ Reversible patch history + undo/**redo** · ✅ add/move/remove/update/set-text plus duplicate,
  table, image, link, list, and page patch ops — `POST /documents/{id}/undo` · `/redo`
- ✅ **Find & replace** across the document (deterministic, redaction-aware, reversible/audited)
  + in-document find with next/prev highlight — `services/docengine/find_replace.py`,
  `POST /documents/{id}/replace`, `components/canvas/FindReplaceModal`
- ✅ **Document zoom** (canvas scale control in the workspace toolbar)
- ✅ Rich formatting (bold/italic/underline/size/color) — toolbar over `update_node` — `components/canvas/FormatToolbar`
- ✅ Block structure editing UI (move up/down, delete) over add/move/remove_node — `components/canvas/NodeRenderer` (BlockWrap)
- ✅ Modify Studio (insert, duplicate, delete, page/slide strip, text, table, image, link, list,
  form-field, and export-safe reversible edits) — `components/canvas/ModifyStudio`
- ✅ Form Builder + fill UI (detect blanks, create/edit/delete fields, required/options metadata,
  reusable template handoff, reversible fill) — `components/canvas/FormsPanel`, `routes_forms.py`
- ✅ Templates UI (save-as-template + browse/stamp-out gallery) — `components/templates/TemplateGallery`, `ToolsMenu`
- ✅ Comment threads UI (anchored to nodes, reply/resolve, versioned) — `services/collab/comments.py`, `components/canvas/CommentsPanel`
- ✅ Track-changes / suggest mode (propose patches; accept→applied+versioned, reject) — `routes_suggestions.py`
- ✅ Templates & styles library (snapshot a doc; stamp out fresh independent docs) — `services/templates`, `routes_templates.py` (UI: `TemplateGallery`)
- 🟡 Real-time co-authoring / presence — **live presence wired** (single-node heartbeat/poll,
  `services/collab/presence.py`, `routes_presence.py`, `PresenceIndicator`): shows everyone
  currently viewing, works out of the box. Multi-node presence (`COLLAB_BACKEND=redis`) and true
  CRDT co-editing remain 🔒 infra.
- ✅ Native slide/spreadsheet editing UX (tractable slice): Modify Studio handles page/slide, text,
  image, and table primitives, **plus structural slide thumbnails** rendered per-page from the model
  (`GET /documents/{id}/slide-thumbnail`, works for any format) and a **cell formula editor**
  (`table_cell.attrs.formula` → a real Excel `=` formula on export, recomputed by Excel on open).
  PowerPoint-grade slide raster + live in-app formula recompute remain provider-gated (need a
  rendering/calc engine). — `writers/image_writer.py`, `writers/xlsx_writer.py`, `ModifyStudio.tsx`
- ✅ **PDF editing — positioned text** (honest scope): write-back covers editing/redacting
  *existing* text spans (matched by bbox), true redaction, **and placing new text that carries a
  bbox**. The canvas now has a **"+ Text" mode** (`FormatToolbar` → click a PDF page to drop a text
  box): the click maps to PDF points and posts an `add_node` patch with a bbox'd run under the page,
  which lands in the export — `tests/integration/test_pdf_add_text_api.py` (API path) and
  `test_pdf_new_text.py` (writer). Paragraph reflow, moving/replacing objects, and native
  form/signature fields still need a PDF SDK provider (surfaced as "PDF native editor: not
  connected") — `writers/pdf_writer.py`

## D. Convert & export
- ✅ DOCX / TXT / PDF (write-back) export
- ✅ Markdown / HTML / CSV / RTF export — `writers/markup.py` (RTF now round-trips: import strips
  control words, export rebuilds a real `.rtf` with paragraphs/bold/italic/tables, redaction-safe)
- ✅ XLSX / PPTX / PNG export from any source format — `writers/{xlsx,pptx,image}_writer.py`
  (XLSX now descends into page nodes; DOCX/PPTX embed real image bytes when persisted)
- ✅ Image persistence — adapters extract image bytes at parse, the upload route writes them to
  blob storage, and DOCX/PPTX exporters embed them instead of `[image: …]` placeholders
- ✅ Page ops: merge / split / reorder / rotate / delete — `services/docengine/pageops.py`
  (in-place ops — rotate / delete / reorder / watermark / compress — now **persist a new version**;
  split / merge / protect remain download-only by design)
- ✅ Compress (PDF) — `pageops.compress_pdf`
- ✅ **Output validation engine** — every export/convert/page-op returns a proof report
  (output opens, page count preserved, **redactions provably unrecoverable**, text retained,
  seal-invalidation flagged). `GET /documents/{id}/export/report` + `X-DocOS-Validation`
  header on downloads — `services/provenance/validation.py`

## E. Sign & agree
- ✅ Integrity seal (HMAC; detects post-seal changes — **not** a legally-binding e-signature) ·
  ✅ Fillable form fields (list + fill) — `routes_forms.py`
- ✅ Approval / multi-party sign-off workflow (ordered or parallel, audited) — `routes_approvals.py`, `services/collab/approvals.py`
- ✅ Bulk send (one packet to many recipients; per-recipient copy + sign-off) — `routes_bulk_send.py`
- 🟡 Legally-binding e-sign (ESIGN/UETA/eIDAS) — **provider seam wired** (`services/esign`,
  `routes_esign.py`): `POST /documents/{id}/signature-request` sends to a regulated provider when
  `SIGNATURE_PROVIDER_URL` + key are set (HMAC-verified webhook updates status); otherwise it applies
  the tamper-evident integrity seal and is explicit that it is **not** legally binding. The legal
  *standing* (CA / KYC / notarization vendor account) is still 🔒.
- ✅ Full CLM (clause library + renewals) — session-scoped `Clause`/`RenewalReminder` (migration
  0009). Save reusable clauses and insert them as reversible `add_node` patches
  (`POST /documents/{id}/insert-clause`); track renewal/expiry dates in-app, sorted by due date with
  overdue/soon urgency, with date auto-suggestions from the deterministic extractor
  (`GET /documents/{id}/renewal-suggestions`). In-app reminders only — email/push delivery needs
  infra. — `services/clm/`, `routes_clm.py`, `components/canvas/ClausesPanel.tsx`,
  `components/clm/RenewalsSection.tsx`

## F. Protect & make trustworthy
- ✅ True redaction on export · ✅ Metadata sanitization · ✅ Document-health panel
- ✅ AI-assisted PII/secret detection → one-click redaction — `services/provenance/sensitive.py`
  (high-precision regex) with an activatable **Presidio** NER seam (`PII_ENGINE=presidio`) for names/
  locations/dates, merged without double-counting — `services/provenance/presidio.py`, `pii.py`
- ✅ Send-Ready Check / Document X-Ray — one verdict (ready/needs-fixes/blocked) composing the
  PII scan, hidden-metadata risk, unapplied redactions and unfilled fields in a single
  cross-format pass, with one-click fixes — `services/provenance/readiness.py`,
  `GET /documents/{id}/readiness`, `components/health-panel/ReadinessPanel.tsx` (downloadable report)
- ✅ Clean Before You Send — `POST /documents/{id}/clean` applies the auto-fixes (strip hidden
  metadata + true-redact PII) as one reversible patch, re-checks, and returns the post-clean
  verdict + a validation **proof** that the redacted text is unrecoverable; clean copy downloads
  via `/export`. PDF embedded /Info + XMP metadata is stripped on the clean export (scoped to
  sanitized docs in `writers/pdf_writer.py`)
- ✅ Un-Redact Test — detect text still recoverable under a PDF's "redactions" (black-box fills /
  redaction annotations); reports recoverable count + verdict (safe/leaky) without echoing the
  text — `services/provenance/redaction_audit.py`, `GET /documents/{id}/redaction-audit`,
  surfaced as an alarm banner in `ReadinessPanel.tsx`
- ✅ Un-Retype (PDF→Excel) — `/tasks/pdf-to-excel` pulls tables + data points out of a PDF/scan into
  Excel/CSV with a "found N data points" reveal, on the table-extraction + xlsx-writer path
- ✅ Fill Once — reusable autofill profile (`FillProfile` table + migration `0008`):
  `GET/PUT /fill-profile` saves field-name→value answers once; `POST /documents/{id}/autofill`
  fills matching blank fields as one reversible patch — `api/routes_profile.py`, FormsPanel UI
- ✅ Private Mode — honest privacy posture + control: session-private docs, "AI off → nothing sent
  to third parties", one-click `DELETE /documents` purge-all (no fake auto-delete claim) —
  `routes_documents.purge_my_documents`, `components/system/PrivacyPanel.tsx`
- ✅ Public no-login tool pages: `/tasks/un-redact-test` (instant reveal) and `/tasks/send-ready-check`
  (→ trust tab), featured on the landing page; per-page SEO metadata via `generateMetadata` in
  `app/tasks/[slug]/page.tsx`. (Layer-1 distribution surface; Chrome extension still ⬜)
- ✅ Password / encrypt / permissions on PDF (AES-256) — `pageops.encrypt_pdf`
- ✅ Accessibility auto-remediation (auto-tag headings, reading order, alt-text) — reversible — `services/provenance/accessibility.py`
- ✅ Malware scan — ClamAV (INSTREAM) wired and **fails closed** when configured but
  unreachable; offline default stays NoopScanner — `services/ingestion/scanner.py`
- ✅ Watermark (text stamp) — `pageops.watermark_pdf`; **permissive (non-AGPL) engine** via
  reportlab overlay + pypdf merge (`PDF_ENGINE=permissive`), parity-tested
- ✅ PDF edit-fidelity: edited spans keep the original font family/weight (base-14 mapping, not a
  flat default) — `writers/pdf_writer.py`; gated by `evals/pdf_fidelity`
- ✅ PDF redaction proof: zero-recoverable-bytes corpus now covers the write-back path, including a
  mixed edit+redact case — `evals/redaction_proof`
- 🟡 DRM — **seam wired** (`services/drm`, `POST /documents/{id}/drm`): applies a rights-management
  provider when `DRM_PROVIDER_URL` is set, else 501 pointing to AES-256 Protect PDF (the honest
  local protection).

## G. Compare, review & collaborate
- ✅ Version DAG + audit log
- ✅ Document compare / diff (two documents, cross-format) — `services/provenance/diff.py`
- ✅ Comment threads (add / reply / resolve / delete, versioned) — `routes_comments.py`
- ✅ Approval workflows (ordered / parallel sign-off, audited) — `routes_approvals.py`
- 🟡 Real-time presence (single-node) wired (see §C); multi-node presence remains 🔒 collaboration infra
- ✅ **Shareable client portal** — token-based `/portal/{token}` read + readiness + sign-off;
  create_recipient_share() for bulk-send creates per-recipient portal URLs — `BulkSendPanel` on Send tab
  lists copyable links; GET `/documents/{id}/bulk-send` includes `portal_url`. `document_shares` migration
  `0011`, `api/routes_share.py`, `api/access.py`, `components/canvas/ShareLinkModal.tsx`,
  `app/portal/[token]/page.tsx`. Pro plan required to create ad-hoc share links (402 on free tier).

## H. Ask AI about it
- ✅ AI editing over the model · ✅ Chat / Q&A with citations · ✅ Summarize — `services/semantic/reader.py`
- ✅ Conversational multi-turn Q&A (history-biased retrieval, cited per turn) — `reader.chat`,
  `POST /documents/{id}/chat`
- ✅ Extract structured data on request — `services/semantic/extract.py`
- ✅ Translate (LLM-backed)
- ✅ Multi-document "notebook" (corpus Q&A, cross-doc citations) — `services/semantic/corpus.py`, `routes_notebook.py`
- ✅ Multi-document **agent** (plan→search→cite across the corpus, read-only) —
  `services/semantic/agents/corpus_executor.py`, `POST /notebook/agent`
- ✅ Grounding/faithfulness gate in CI (deterministic, offline): the Q&A answer must trace stated
  numbers to citations and abstain on absent facts — `evals/agent_quality/harness.py::score_grounding`
- ✅ Token-usage metering on the agent loop + Anthropic prompt-caching of the system prompt —
  `llm/base.py::merge_usage`, `llm/anthropic.py`
- 🟡 Doc → audio — **seam wired** (`services/tts`, `GET /documents/{id}/audio`): streams narrated,
  redaction-aware audio when `TTS_PROVIDER_URL` is set, else an honest 501. No offline TTS engine.

## I. Store, find & manage
- ✅ **Registered accounts** — email/password register/login/logout/me; signed `docos_uid` cookie;
  anonymous-session docs/templates/clauses/fill-profiles claimed on login — `users` table migration
  `0011`, `api/routes_auth.py`, `services/auth/`, `app/login`, `app/signup`,
  `components/auth/AccountMenu.tsx`. List queries use session **or** user ownership.
- ✅ Per-session document ownership — every document is owned by a signed anonymous-session
  cookie; cross-session access 404s (no IDOR). One authz chokepoint — `api/access.py`,
  `api/session.py`.
- ✅ Upload hardening — streamed size cap (413), per-session upload rate limit (429),
  ingest `JobRecord` seam — `api/ratelimit.py`, `routes_documents.py`
- ✅ Verifiable deletion — failed blob deletes recorded as `BlobTombstone` + audited (not
  swallowed); sweeper retries until resolved — `routes_documents.py`,
  `services/provenance/deletion.py`
- ✅ Encryption-at-rest — opt-in AES-256-GCM blob wrapper (offline default plaintext;
  transparent to callers, legacy-plaintext safe) — `storage/encrypted.py`
- ✅ Document list / CRUD · ✅ Blob storage (local/S3)
- ✅ Tags + full-text search across all docs (redaction-aware) — `routes_library.py`; tags UI on
  document workspace + library list — `TagsPanel.tsx`, `DocumentList.tsx`
- ✅ **Monetization seam** — `/pricing`, Stripe Checkout + webhook when `STRIPE_*` keys set,
  `subscriptions` table, plan gating (portal links = Pro) — `api/routes_billing.py`,
  `services/billing/`, `app/pricing`. Honest 501 when billing not configured.
- ✅ Semantic search across the corpus (BM25; offline) — `services/semantic/corpus.py`
- ✅ True semantic recall via embeddings, fused with BM25 (RRF) — `services/semantic/embeddings.py`,
  `services/semantic/search.py`. Offline `EMBEDDING_PROVIDER=local` (fastembed, no API key) or
  `openai`; default-off → pure BM25. Persistent on-disk embedding cache.
- 🟡 Drive/Dropbox/Box/SharePoint/Slack integrations — OAuth seam wired (see §A)
- 🔒 Mobile **apps** (native clients) — PWA capture is wired (see §A); native apps still need clients

---

### Why some items are 🔒 (not faked)
Real-time collaboration (CRDT/WebSocket fleet), legally-binding signatures (a trusted CA,
KYC/identity, notarization, payment rails), mobile capture (native apps), and third-party
cloud/IDP integrations (OAuth secrets, paid APIs) require infrastructure, credentials, or
legal standing that can't be stood up inside this repo. Their seams exist (e.g. `NoopScanner`,
the `LLMClient` provider switch, the `BlobStore` abstraction) so they can be wired when that
infrastructure is provisioned — rather than shipping a fake that claims compliance it doesn't have.

## J. Replacement-grade hardening lane
- ✅ Liveness/readiness probes: `/live` (process up) + `/ready` (DB tables exist + blob storage
  writable → 503 otherwise; Railway healthcheck points here so a broken/volumeless deploy fails
  fast). `/health` stays a 200 status summary the UI reads — `api/routes_health.py`.
- ✅ Provider/storage truthing in `/health` (AI provider, Office/PDF native-editor state, storage,
  SQLite vs Postgres, billing, e-sign/IDP/TTS/DRM/cloud) surfaced by the home page **System status**
  panel — `components/system/SystemStatusPanel.tsx`.
- ✅ Enterprise hardening: per-session+IP rate limiting on expensive ops (clean / redaction-audit /
  autofill) via `enforce_op_rate`; input bounds on the Fill-Once profile (entry count + key/value
  length → 422); page-scan caps (`max_scan_pages`) so a many-page PDF can't exhaust CPU during table
  detection or the un-redact test; cross-session/tenant isolation enforced (404) and covered by
  `tests/integration/test_enterprise_hardening.py`.
- ✅ Both Docker images install the Anthropic **and** OpenAI provider extras so a configured
  `OPENAI_API_KEY` can't crash on a missing SDK at runtime.
- ✅ Windows-safe web build: local `pnpm --filter @docos/web build` skips Next standalone
  symlink creation on Windows, while Linux/Railway can keep standalone output through
  `DOCOS_NEXT_STANDALONE=1`.
- ✅ Read-only production smoke harness: `pnpm smoke:production` checks the Railway home page,
  `/api/health`, and OpenAPI without mutating production data. New hardening routes can be
  required with `DOCOS_REQUIRE_HARDENING_OPENAPI=1` after a fresh deploy.
- ✅ Stress test lane: `pytest -m stress` covers primary uploads, malformed/oversized files,
  patch/undo loops, editor sessions, destructive-action planning, and template variables.
- ✅ Browser E2E lane: Playwright smoke covers the task grid, template workflow entry, signup/login/pricing
  pages, and wired marketing sections — `e2e/task-grid.spec.ts`, `e2e/auth-portal.spec.ts`.
- ✅ Production smokes: read-only home/health/OpenAPI (`smoke:production`), client-packet API/UI,
  editor smoke, auth/billing/portal OpenAPI seam (`smoke:production:auth`).
- ✅ Embedded editor session APIs: `/documents/{id}/editor/session`,
  `/documents/{id}/editor/session/{session_id}`, `/save`, and `/sync` create auditable
  native-editor sessions. DOCX/XLSX/PPTX use an ONLYOFFICE-compatible provider only when
  configured; otherwise the API returns an honest local-basic warning.
- ✅ DocumentOpsAgent planning API: `/documents/{id}/ops-agent/plan` returns deterministic
  classify/extract/validate/template-fill/approval/redact/export plans. Destructive work is
  approval-gated and legal e-sign claims remain blocked until a regulated signing provider exists.
- ✅ Local agent eval harness: `pnpm eval:document-ops` checks workflow correctness, approval
  gates, action reasons, and legal-signing honesty.
- 🟡 Native PDF editing: still labeled basic unless `PDF_EDITOR_PROVIDER=external` and
  `PDF_EDITOR_URL` point at a licensed PDF editor provider.
- ✅ Web resilience: route-segment + global error boundaries, branded 404, and a loading fallback
  (`app/{error,global-error,not-found,loading}.tsx`); the react-query client uses production
  defaults (1 retry, staleTime, no refetch-on-focus) so a failing backend isn't hammered.
- ✅ HTTP security headers on every response (`next.config.mjs` `headers()`): a Next-14-safe CSP
  (same-origin `connect-src`, `data:`/`blob:` images for previews/downloads), `X-Content-Type-Options`,
  `X-Frame-Options` + `frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`, and HSTS in prod.
- ✅ Request-correlated observability: `RequestContextMiddleware` binds an `X-Request-ID` (inbound or
  generated) + one access-log line per request; a global exception handler returns a clean
  `{detail, request_id}` envelope that never leaks tracebacks. `LOG_FORMAT=json` for structured logs.
  Sentry is an env-gated seam (`SENTRY_DSN` + the optional `[sentry]` extra) — inert when unset —
  `api/observability.py`.
- ✅ Burst rate-limiting extended to all costly endpoints (AI ask/summarize/translate, notebook,
  ops-agent, export/searchable-pdf, page ops) via `enforce_op_rate` — a generous per-minute
  session+IP burst guard (not a total/daily cap, so the "unlimited" promise holds); preview +
  slide-thumbnail stay unlimited for the canvas. Auth register/login and portal token lookups
  have dedicated per-IP buckets — `api/ratelimit.py`.
