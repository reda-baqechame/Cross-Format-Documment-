# ADR-002: PdfEngine migration (AGPL exit)

## Status

Proposed — permissive PdfEngine path must reach parity before AGPL dependency removal.

## Context

PyMuPDF (`fitz`) is used for PDF parse/page-ops in adapters and golden fixture generation. It is AGPL-licensed.

## Decision

1. Keep PyMuPDF behind `PdfAdapter` and page-ops seams until a permissive engine (e.g. pypdf + pdfium render path) passes golden PDF fixtures.
2. New export/searchable-PDF work must go through canonical model writers first.
3. CI golden_packets PDF cases are the parity gate.

## Consequences

- No silent AGPL removal until `evals/golden_packets` PDF cases pass on the alternate engine.
- Document infra-gated e-sign separately (ADR pending provider).
