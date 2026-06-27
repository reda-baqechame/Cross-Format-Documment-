# Document-fidelity eval lab

A deterministic, offline benchmark for the document **plumbing** — parse fidelity, OCR confidence,
table structure, export openability, and redaction unrecoverability. No LLM, no network. This is how
we stop guessing about extraction quality and engineer it against numbers.

## Run

```bash
python evals/document_fidelity/run_local.py
```

It builds a representative canonical document, runs every metric, prints a JSON report, and exits
non-zero if any metric regresses below its threshold (so it can gate CI like the `document_ops` lab).

## Metrics (`metrics/`)

| Metric | Measures |
|---|---|
| `layout_score` | reading-order coverage + monotonicity of top-level blocks |
| `ocr_score` | mean per-run OCR confidence (0–1) |
| `table_score` | recovered table cells ÷ expected cells |
| `export_score` | export openability + visible-word retention through the real pipeline |
| `redaction_score` | a redacted secret is truly absent from exported bytes (1.0 = unrecoverable) |

Each metric is a pure function over a `CanonicalDocument` (and, where needed, the adapter registry),
so they are reusable from unit tests and from per-format corpus runs.

## Corpus (`samples/`)

Drop real-world files under `samples/{pdf,scanned_pdf,docx,xlsx,pptx,images,corrupt,redaction}/` to
extend coverage beyond the synthetic in-memory sample. Track per-format: parse-success rate, OCR
accuracy, table accuracy, layout preservation, export openability, redaction unrecoverability, and
processing time / memory per page. Keep the corpus small and license-clean (own or public-domain
documents only).

## Roadmap

- Wire `OCR_ENGINE=paddle` / `PARSER_ENGINE=docling` runs to compare engines on the same corpus.
- Add cost-per-document and LLM-patch-validity once the AI orchestration layer lands.
