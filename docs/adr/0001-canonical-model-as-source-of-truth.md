# ADR 0001 — The canonical model is the single source of truth

- **Status:** Accepted
- **Date:** 2026-06-15

## Context

The document market is fragmented by file type: PDF tools, office suites, and signing
platforms each own a slice and break at the seams (PDF↔Word conversion, lost comments,
unsafe redaction). A product that promises "edit any document" must avoid re-building
every feature once per format.

We also need AI-assisted editing that is safe for legal/compliance content — i.e. edits
that are previewable, reversible, and auditable — rather than whole-file regeneration.

## Decision

Adopt a single **canonical document model** (a typed node graph) as the source of truth.

- Format adapters parse files *into* the model and export *from* it. The rest of the
  system is format-agnostic.
- The frontend canvas renders *from* the model, not from the raw file.
- All edits are expressed as **reversible patches** against the model, carrying their own
  inverse and originating intent.
- Versioning uses a canonical content hash of the model, so versions de-duplicate and
  diffs are structural rather than byte-level.

## Consequences

**Positive**
- Editing, diffing, redaction, accessibility, and health are implemented once.
- AI edits are bounded, previewable, reversible, and auditable.
- New formats are additive: implement one `FormatAdapter`.

**Negative / costs**
- Round-trip fidelity depends on adapters preserving format-specific data; we mitigate by
  keeping unmapped data in node `attrs` and treating fidelity as a release gate.
- High-fidelity export (esp. PDF) is non-trivial and is deferred behind the parse path.

## Alternatives considered

- **Per-format editors stitched together** — rejected; this is exactly the fragmentation
  the product exists to remove.
- **Feed raw files to an LLM** — rejected; loses layout/structure and makes edits
  unbounded and unauditable.
