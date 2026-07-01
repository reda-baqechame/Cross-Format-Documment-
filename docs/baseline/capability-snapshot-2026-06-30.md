# Capability & test baseline — 2026-06-30

Captured at the start of the `expert/packet-audit-and-engine-hardening` branch (off `origin/main` @ `c9391e9`)
to make the "nothing breaks / provable improvement" guarantee auditable.

## Toolchain baseline (local)
- Python 3.14 (CI uses 3.11), uv 0.10.11, node v24.11, pnpm 9.0.0
- Backend `docos` importable; pytest 9.1.0; **ruff clean**
- Tesseract NOT installed locally → OCR-dependent matrix steps run on CI only
- Baseline test run: `test_pack_*` (6 files) + `test_capabilities` = **40 passed, 0 failed**
  (full suite too slow for one local run; CI runs the complete matrix)

## Capability ledger snapshot (`GET /capabilities`, offline defaults)

Proof run: `production-tool-matrix-2026-06-27`. State vocabulary:
`verified | degraded | provider_gated | disabled | broken | claim_without_proof`.

| Capability | State (offline) | Engine | Proof |
|---|---|---|---|
| upload_store | **degraded** (local+sqlite) | parser:native | Upload userPdf |
| convert_formats | **degraded** | native-writers | Export PDF→docx |
| pdf_edit_text | verified | pdf-render:pymupdf | Modify PDF text ⚠AGPL |
| pdf_organize | verified | page-ops (permissive if configured) | Merge PDFs |
| pdf_compress | verified | compress (permissive if configured) | Compress PDF |
| pdf_watermark | verified | pymupdf-pageops | Watermark PDF ⚠AGPL |
| pdf_protect | verified | encrypt (permissive if configured) | Protect PDF |
| redaction | verified | pii:regex | eval:redaction_proof ⚠AGPL(PDF) |
| metadata_sanitize | verified | pymupdf-scrub | Clean before send ⚠AGPL |
| readiness_check | verified | readiness | Document health panel |
| ocr | verified | ocr:tesseract | Searchable PDF (PNG scan) |
| searchable_pdf | verified | pymupdf-writer | Searchable PDF (user doc) ⚠AGPL |
| search (BM25) | verified | bm25-keyword+stemming | eval:search_retrieval |
| semantic_search | **degraded** (BM25 fallback) | bm25-fallback | — |
| ai_ask_summarize | **provider_gated** | llm:noop | — |
| ai_edit | **provider_gated** | llm:noop | Ops agent plan |
| ai_agent | **degraded** (offline plan+read) | agent:noop | eval:document_ops |
| translate | **provider_gated** | llm:noop | — |
| tts | **provider_gated** | tts:none | — |
| esign | **provider_gated** | signature:seal | Integrity seal (HMAC, not legal) |
| drm | **provider_gated** | drm:none | — |
| idp | **provider_gated** | idp:local | — |
| handwriting | **provider_gated** | handwriting:none | — |
| office_editor | **provider_gated** | office-editor:local | — |
| pdf_editor | **provider_gated** | pdf-editor:basic | — |
| billing | **provider_gated** | none | — |
| cloud_integrations | **provider_gated** | oauth | List integrations |
| collaboration | verified (single-node) | presence | — |
| pack_import_export | verified | pack:import_export | test:pack_import_export |
| pack_finance_ap | verified | pack:finance | test:pack_finance |
| pack_contracts | verified | pack:contracts | test:pack_contracts |
| pack_hr_onboarding | verified | pack:hr | test:pack_hr |
| pack_insurance | verified | pack:insurance | test:pack_insurance |
| workflow_recipes | verified | workflow:recipes | test:workflow_recipes |
| malware_scan | verified (heuristic) | scanner:heuristic | test:scanner_content_defense |

## What this plan must improve (provable deltas)
1. Add **`pack_audit`** + per-vertical **`expert_verified`** capabilities (new state) gated by golden packets.
2. Remove the **⚠AGPL** flag from the PDF capabilities by finishing the permissive engine (ADR-002).
3. Add the **Command Center** UI surface (currently `claim_without_proof` / ⬜ in roadmap).
4. Add the **public packet-audit benchmark** so `market_superior` becomes measurable, not asserted.

These four deltas are the difference between "feature exists" and "expert-grade, better-than-market, real results".
