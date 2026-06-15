# Privacy modes

Privacy is configuration, not a fork. `PRIVACY_MODE` plus the backend settings decide
which concrete implementation is wired behind each interface in `deps.py`. Sensitive
deployments can run fully offline; cloud deployments can use hosted providers.

| Concern | `offline` | `enterprise` | `cloud` |
|---|---|---|---|
| Blob storage | `LocalBlobStore` (filesystem) | `S3BlobStore` (self-hosted MinIO/S3) | `S3BlobStore` (managed) |
| LLM | `LocalNoopClient` (no egress) | self-hosted / approved provider | hosted provider |
| OCR | local Tesseract | local Tesseract | managed OCR allowed |
| Malware scan | `NoopScanner` (dev only) | `ClamAVScanner` | managed scanning |
| Audit retention | local | enforced retention | enforced retention |

## How the swap works

`deps.py` reads `Settings` and returns the right implementation:

- `get_blob_store()` → local vs S3 by `BLOB_BACKEND`.
- `get_llm_client()` → noop / OpenAI / Anthropic by `LLM_PROVIDER`.
- `get_ingestion_gateway()` → injects the configured scanner.

Because every caller depends on the **interface** (`BlobStore`, `LLMClient`,
`MalwareScanner`), no business logic changes between modes.

## Defaults

The shipped `.env.example` defaults to `offline`: local blobs, the noop LLM, and the
noop scanner — so the system runs end to end with zero external dependencies or data
egress. Harden these before handling real sensitive content (enable a real scanner,
move blobs to encrypted object storage, set audit retention).
