# docos — backend

FastAPI service hosting the **canonical document model** and the five document services.

## Package map (`src/docos`)

| Path | Purpose |
|---|---|
| `main.py` | FastAPI app factory; mounts routers; `/health`. |
| `settings.py` | Pydantic Settings (privacy mode, backends, secrets). |
| `deps.py` | Dependency-injection providers (db session, blob store, queue, services). |
| `model/` | **Canonical document model** — node graph, document root, reversible patches, serialization. |
| `services/ingestion/` | Allow-list, magic-byte sniff, malware scan, sandboxed staging. |
| `services/docengine/` | Per-format `FormatAdapter`s + registry. TXT & DOCX are functional. |
| `services/ocr/` | OCR & structure service (stub). |
| `services/semantic/` | Intent → reversible patch orchestration + pluggable `LLMClient`. |
| `services/provenance/` | Versioning, audit, labels, redaction state, document-health. |
| `storage/` | `BlobStore` ABC + local (default) and S3 (stub) impls. |
| `queue/` | Celery app + tasks. |
| `db/` | SQLAlchemy base + ORM models. |
| `api/` | HTTP routers + request/response schemas. |

## Local development

```bash
uv sync                 # or: pip install -e ".[dev]"
alembic upgrade head
uvicorn docos.main:app --reload
pytest -q
```

## Design rules

1. **The canonical model is the single source of truth.** Adapters parse *into* it; the frontend
   renders *from* it; exporters serialize *from* it.
2. **Edits are reversible patches**, never whole-file regeneration (`model/patch.py`).
3. **Services depend on interfaces** (`services/*/interface.py`), never concrete vendors — so each
   format/provider/scanner is pluggable and the privacy mode swaps implementations via config.
