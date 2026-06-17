# Services

Each service owns one boundary and exposes an interface (`services/<name>/interface.py`).
Implementations are pluggable; the privacy mode and settings decide which are wired.

| Service | Interface | Functional today | Stubbed extension points |
|---|---|---|---|
| Ingestion & safety | `IngestionGateway` | allow-list, magic-byte sniff, noop scan, local staging | `ClamAVScanner`, real `Sandbox` |
| Document engine | `FormatAdapter` | parse for all formats; DOCX/XLSX/PPTX/PNG/MD/HTML/CSV/PDF export | RTF export; faithful PDF text-reflow on write-back; in-engine previews |
| OCR & structure | `OcrStructureService` | — | `TesseractOcr` cleanup/recognize/tables/reading-order |
| Semantic orchestration | `SemanticOrchestrator` | `apply`/`revert` patches; noop `interpret` | OpenAI/Anthropic `LLMClient`, real intent→patch planning |
| Provenance & policy | `ProvenancePolicyService` | versions, audit, labels, health, metadata-sanitize patch | richer policy engine, signature verification |

## Adding a format adapter

1. Implement `FormatAdapter` in `services/docengine/adapters/<fmt>.py`
   (`parse`, `render_preview`, `export`; set `format_id` and `supported_mimes`).
2. Register it in `services/docengine/registry.py::default_registry`.
3. Add the MIME to `ALLOWED_MIME_TYPES` and the format map in `ingestion/gateway.py`.
4. Add fixtures + a unit test mirroring `tests/unit/test_docx_adapter.py`.

## Adding an LLM provider

1. Implement `LLMClient.complete` in `services/semantic/llm/<provider>.py`.
2. Wire it in `deps.py::get_llm_client` behind a `LLM_PROVIDER` value.
3. Keep the orchestrator depending only on the `LLMClient` interface.
