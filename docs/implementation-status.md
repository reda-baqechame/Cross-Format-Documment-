# Implementation Status — the "everything people do with documents" superset

Tracks every capability from [`competitive-analysis.md`](competitive-analysis.md) §4 against
what is actually built. Legend: ✅ done · 🟡 partial · 🔜 in progress · ⬜ not started ·
🔒 needs external infra/services (scaffolded or deferred, with reason).

This file is the source of truth for "don't forget anything." Update it as features land.

## A. Capture & ingest
- ✅ Upload TXT/DOCX/PDF/XLSX/PPTX/RTF/image (magic-byte validated) — `services/ingestion`
- 🟡 OCR scans (Tesseract best-effort) — `services/ocr` structure extraction still a stub
- 🔒 Mobile camera capture + deskew — needs native/mobile client
- 🔒 Import from Drive/Dropbox/Box/email/URL — needs OAuth + provider credentials
- ⬜ Handwriting OCR · ⬜ Bulk/folder import

## B. Understand it (OCR, IDP, structure)
- ✅ Parse to structured model (nodes, reading order, tables)
- 🟡 Table extraction
- ✅ Key-value / entity extraction (dates, emails, money, etc.) — `services/semantic/extract.py`
- ⬜ Document classification · ⬜ Searchable-PDF generation
- 🔒 Cloud IDP (ABBYY/Textract/Google) parity — external APIs/keys

## C. Edit & author
- ✅ Inline text edit · ✅ explicit structural ops · ✅ AI natural-language edit (validated)
- ✅ Reversible patch history + undo · ✅ add_node / move_node ops (full reversible set)
- 🟡 Rich formatting (bold/italic/size/color)
- 🔒 Real-time co-authoring / presence — needs WebSocket + CRDT infra
- ⬜ Comments/track-changes UI · ⬜ Templates & styles library · ⬜ Slide/spreadsheet editing UX

## D. Convert & export
- ✅ DOCX / TXT / PDF (write-back) export
- ✅ Markdown / HTML / CSV export — `writers/markup.py`
- ✅ Page ops: merge / split / reorder / rotate / delete — `services/docengine/pageops.py`
- ⬜ XLSX / PPTX export · ⬜ image export · ⬜ compress

## E. Sign & agree
- ✅ Tamper-evident e-signature (HMAC) · 🟡 fillable form fields (model + fill API)
- 🔒 Legally-binding e-sign (ESIGN/UETA/eIDAS), PKI certs, identity verification, notarization,
  payments — needs a certificate authority / regulated signing & KYC provider
- ⬜ Multi-party signing order / bulk send · ⬜ Approval workflows / CLM

## F. Protect & make trustworthy
- ✅ True redaction on export · ✅ Metadata sanitization · ✅ Document-health panel
- ✅ AI-assisted PII/secret detection → one-click redaction — `services/provenance/sensitive.py`
- 🔜 Password / encrypt / permissions on PDF export
- 🟡 Accessibility auto-remediation (auto-tag headings, reading order, alt-text placeholders)
- 🔒 Malware scan — needs ClamAV daemon (NoopScanner seam ready)
- ⬜ Watermark / DRM

## G. Compare, review & collaborate
- ✅ Version DAG + audit log
- ✅ Document compare / diff (two documents, cross-format) — `services/provenance/diff.py`
- 🔒 Real-time presence / shareable links with live perms — collaboration infra
- ⬜ Comment threads · ⬜ Approvals

## H. Ask AI about it
- ✅ AI editing over the model · ✅ Chat / Q&A with citations · ✅ Summarize — `services/semantic/reader.py`
- ✅ Extract structured data on request — `services/semantic/extract.py`
- 🟡 Translate (LLM-only when a provider is set) · ⬜ Multi-document "notebook"
- 🔒 Doc → audio/podcast — needs a TTS service

## I. Store, find & manage
- ✅ Document list / CRUD · ✅ Blob storage (local/S3)
- 🔜 Folders / tags + full-text search across all docs — `services/library`
- 🔒 Drive/Dropbox/Box/SharePoint/Slack integrations — OAuth + creds
- 🔒 Mobile apps — native clients
- ⬜ Semantic search across the corpus

---

### Why some items are 🔒 (not faked)
Real-time collaboration (CRDT/WebSocket fleet), legally-binding signatures (a trusted CA,
KYC/identity, notarization, payment rails), mobile capture (native apps), and third-party
cloud/IDP integrations (OAuth secrets, paid APIs) require infrastructure, credentials, or
legal standing that can't be stood up inside this repo. Their seams exist (e.g. `NoopScanner`,
the `LLMClient` provider switch, the `BlobStore` abstraction) so they can be wired when that
infrastructure is provisioned — rather than shipping a fake that claims compliance it doesn't have.
