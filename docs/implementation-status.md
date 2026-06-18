# Implementation Status — the "everything people do with documents" superset

Tracks every capability from [`competitive-analysis.md`](competitive-analysis.md) §4 against
what is actually built. Legend: ✅ done · 🟡 partial · 🔜 in progress · ⬜ not started ·
🔒 needs external infra/services (scaffolded or deferred, with reason).

This file is the source of truth for "don't forget anything." Update it as features land.

## A. Capture & ingest
- ✅ Upload TXT/DOCX/PDF/XLSX/PPTX/RTF/image (magic-byte validated, OOXML verified by package
  contents not extension, zip-bomb limits) — `services/ingestion`
- ✅ Bulk/multi-file import (drag many files; per-file result) — `components/upload/UploadDropzone`
- 🟡 OCR scans (Tesseract best-effort) — `services/ocr` structure extraction still a stub
- 🔒 Mobile camera capture + deskew — needs native/mobile client
- 🔒 Import from Drive/Dropbox/Box/email/URL — needs OAuth + provider credentials
- ⬜ Handwriting OCR

## B. Understand it (OCR, IDP, structure)
- ✅ Parse to structured model (nodes, reading order, tables)
- 🟡 Table extraction
- ✅ Key-value / entity extraction (dates, emails, money, etc.) — `services/semantic/extract.py`
- ✅ Document classification — `services/semantic/classify.py`
- ✅ **Document Skills + Autopilot** — recognizes the ~15-category document-purpose taxonomy,
  extracts typed fields per purpose with confidence, runs checks (e.g. invoice totals), flags
  what needs human review, and recommends next actions. Deep skills: invoice, contract, résumé;
  generic fallback for every other recognized type. `GET /documents/{id}/autopilot` +
  Autopilot workspace tab — `services/semantic/skills/`
- ✅ Searchable-PDF generation (invisible OCR layer for scans; born-digital text otherwise) — `writers/searchable_pdf.py`
- 🔒 Cloud IDP (ABBYY/Textract/Google) parity — external APIs/keys

## C. Edit & author
- ✅ Inline text edit · ✅ explicit structural ops · ✅ AI natural-language edit (validated)
- ✅ Reversible patch history + undo · ✅ add_node / move_node ops (full reversible set)
- ✅ Rich formatting (bold/italic/underline/size/color) — toolbar over `update_node` — `components/canvas/FormatToolbar`
- ✅ Comment threads UI (anchored to nodes, reply/resolve, versioned) — `services/collab/comments.py`, `components/canvas/CommentsPanel`
- ✅ Track-changes / suggest mode (propose patches; accept→applied+versioned, reject) — `routes_suggestions.py`
- ✅ Templates & styles library (snapshot a doc; stamp out fresh independent docs) — `services/templates`, `routes_templates.py`
- 🔒 Real-time co-authoring / presence — needs WebSocket + CRDT infra
- ⬜ Slide/spreadsheet editing UX

## D. Convert & export
- ✅ DOCX / TXT / PDF (write-back) export
- ✅ Markdown / HTML / CSV export — `writers/markup.py`
- ✅ XLSX / PPTX / PNG export from any source format — `writers/{xlsx,pptx,image}_writer.py`
- ✅ Page ops: merge / split / reorder / rotate / delete — `services/docengine/pageops.py`
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
