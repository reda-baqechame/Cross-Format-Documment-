# Implementation Status — the "everything people do with documents" superset

Tracks every capability from [`competitive-analysis.md`](competitive-analysis.md) §4 against
what is actually built. Legend: ✅ done · 🟡 partial · 🔜 in progress · ⬜ not started ·
🔒 needs external infra/services (scaffolded or deferred, with reason).

This file is the source of truth for "don't forget anything." Update it as features land.

## A. Capture & ingest
- ✅ Upload TXT/DOCX/PDF/XLSX/PPTX/RTF/MD/CSV/HTML/image (magic-byte validated, OOXML verified by package
  contents not extension, zip-bomb limits) — `services/ingestion`
- ✅ First-class Markdown / CSV / HTML import adapters — `services/docengine/adapters`
- ✅ Bulk/multi-file import (drag many files; per-file result) — `components/upload/UploadDropzone`
- ✅ OCR structure extraction — `TesseractOcr` recognises positioned, confidence-scored word runs
  (`image_to_data` → `RunNode` + bbox + `attrs.confidence`/`ocr_review`), geometric reading order,
  Pillow cleanup; the image adapter prefers structured OCR and falls back to flat text. Scanned-grid
  table detection still deferred. — `services/ocr/tesseract.py`, `adapters/image.py`
- 🔒 Mobile camera capture + deskew — needs native/mobile client
- 🔒 Import from Drive/Dropbox/Box/email/URL — needs OAuth + provider credentials
- 🔒 ODT / EPUB / XML / JSON / Google Docs / Sheets / Slides imports — future adapters or OAuth integrations
- ⬜ Handwriting OCR

## B. Understand it (OCR, IDP, structure)
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
- 🔒 Cloud IDP (ABBYY/Textract/Google) parity — external APIs/keys

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
- 🔒 Real-time co-authoring / presence — needs WebSocket + CRDT infra
- 🟡 Native slide/spreadsheet editing UX (Modify Studio handles page/slide, text, image, and
  table primitives; high-fidelity slide thumbnails/formula editor still pending)
- 🟡 **PDF editing — known limits** (honest scope): write-back covers editing/redacting *existing*
  text spans (matched by bbox), true redaction, **and placing new text that carries a bbox**
  (positioned new text now lands in the export — `tests/integration/test_pdf_new_text.py`). The
  canvas "Add text" doesn't yet capture an on-page position for PDFs, so UI-added text currently
  flows to DOCX/TXT exports. Paragraph reflow, moving/replacing objects, and native form/signature
  fields still need a PDF SDK provider (surfaced as "PDF native editor: not connected") —
  `writers/pdf_writer.py`

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
- 🔒 Legally-binding e-sign (ESIGN/UETA/eIDAS), PKI certs, identity verification, notarization,
  payments — needs a certificate authority / regulated signing & KYC provider
- ⬜ Full CLM (clause library, renewals)

## F. Protect & make trustworthy
- ✅ True redaction on export · ✅ Metadata sanitization · ✅ Document-health panel
- ✅ AI-assisted PII/secret detection → one-click redaction — `services/provenance/sensitive.py`
- ✅ Send-Ready Check / Document X-Ray — one verdict (ready/needs-fixes/blocked) composing the
  PII scan, hidden-metadata risk, unapplied redactions and unfilled fields in a single
  cross-format pass, with one-click fixes — `services/provenance/readiness.py`,
  `GET /documents/{id}/readiness`, `components/health-panel/ReadinessPanel.tsx`
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
- ✅ Watermark (text stamp) — `pageops.watermark_pdf` · ⬜ DRM

## G. Compare, review & collaborate
- ✅ Version DAG + audit log
- ✅ Document compare / diff (two documents, cross-format) — `services/provenance/diff.py`
- ✅ Comment threads (add / reply / resolve / delete, versioned) — `routes_comments.py`
- ✅ Approval workflows (ordered / parallel sign-off, audited) — `routes_approvals.py`
- 🔒 Real-time presence / shareable links with live perms — collaboration infra

## H. Ask AI about it
- ✅ AI editing over the model · ✅ Chat / Q&A with citations · ✅ Summarize — `services/semantic/reader.py`
- ✅ Extract structured data on request — `services/semantic/extract.py`
- ✅ Translate (LLM-backed)
- ✅ Multi-document "notebook" (corpus Q&A, cross-doc citations) — `services/semantic/corpus.py`, `routes_notebook.py`
- 🔒 Doc → audio/podcast — needs a TTS service

## I. Store, find & manage
- ✅ Per-session document ownership — every document is owned by a signed anonymous-session
  cookie; cross-session access 404s (no IDOR). One authz chokepoint — `api/access.py`,
  `api/session.py`. Registered-user *claim* seam reserved (`Document.owner_user_id`).
- ✅ Upload hardening — streamed size cap (413), per-session upload rate limit (429),
  ingest `JobRecord` seam — `api/ratelimit.py`, `routes_documents.py`
- ✅ Verifiable deletion — failed blob deletes recorded as `BlobTombstone` + audited (not
  swallowed); sweeper retries until resolved — `routes_documents.py`,
  `services/provenance/deletion.py`
- ✅ Encryption-at-rest — opt-in AES-256-GCM blob wrapper (offline default plaintext;
  transparent to callers, legacy-plaintext safe) — `storage/encrypted.py`
- ✅ Document list / CRUD · ✅ Blob storage (local/S3)
- ✅ Tags + full-text search across all docs (redaction-aware) — `routes_library.py`
- ✅ Semantic search across the corpus (TF-IDF cosine; offline) — `services/semantic/corpus.py`
- 🔒 Drive/Dropbox/Box/SharePoint/Slack integrations — OAuth + creds
- 🔒 Mobile apps — native clients

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
  SQLite vs Postgres) surfaced by the home page **System status** panel — `components/system/SystemStatusPanel.tsx`.
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
- ✅ Browser E2E lane: Playwright smoke covers the task grid and template workflow entry.
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
