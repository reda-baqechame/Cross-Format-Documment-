# ADR-002 — Removing the AGPL PyMuPDF dependency (Phase C)

Status: **In progress / blocked on parity, documented here so it isn't re-derived.**
Date: 2026-06-28

## Context

PyMuPDF (`fitz`) is AGPL-3.0, which conflicts with the closed-SaaS license policy. The CI license
gate (`backend/scripts/check_licenses.py`) carries a single, documented exception for it. Phase C's
goal is to remove that exception by replacing PyMuPDF behind the existing `PdfEngine` / `parser_engine`
seams — **only after** security, fidelity, performance, and feature parity pass (per the core
invariant; we never ship a silent fidelity regression).

`fitz` remains in 5 modules, used for three distinct capability classes:

| Capability | fitz API | Permissive replacement? |
|---|---|---|
| Page rendering (raster) | `get_pixmap`, `Matrix` | ✅ **Already migrated** — `pdfium.py` (`PDF_RENDER_ENGINE=pdfium`, pypdfium2, Apache/BSD). |
| Structural page-ops, encrypt, compress | (via `pageops`) | ✅ **Already migrated** — `pdfengine/permissive_engine.py` (pypdf + pikepdf), parity-tested. |
| Watermark | `insert_textbox` overlay | ✅ **Migrated** — `permissive_engine.watermark_pdf` (reportlab overlay + pypdf merge), parity-tested. |
| **Rich text parse** | `get_text("dict")` → blocks/lines/spans with bold/italic/font/size/color/bbox | ⚠️ **No drop-in.** pypdfium2 exposes characters/positions but **not** span formatting. |
| **Table detection** | `find_tables()` | ⚠️ **No equivalent** in pypdfium2/pypdf. |
| **Redaction burn-in** | `add_redact_annot` + `apply_redactions` + `scrub` | ⚠️ **Effectively fitz-unique** — true content removal from the PDF content stream. |

## Decision

**Do not migrate the parse/redaction paths to pypdfium2.** Validated: pypdfium2 cannot reproduce
span-level formatting or detect tables, so routing `adapters/pdf.py` through it would lose
bold/italic/font/colour and all table structure — a fidelity regression that fails the release gate
"unchanged PDF content preserves text, tables, formulas, image count, page order".

The correct permissive replacements are:

1. **Parsing → Docling** (MIT). A `parser_engine="docling"` seam already exists in `settings.py`.
   Path to done: install Docling in an extra, map its layout/table output onto the canonical model,
   and prove parity against the golden corpus (text, tables, image count, reading order) before
   flipping the default. Docling brings *better* table/layout structure, so this is an upgrade, not
   just a swap.
2. **Redaction burn-in → permissive content-stream surgery** (pikepdf + a glyph-removal pass) with a
   dedicated **recoverable-string proof corpus**: export bytes must contain zero recoverable target
   strings in text, metadata, objects, or streams. This is security-critical and must not be rushed;
   it ships only with that proof suite green.
3. **Searchable-PDF invisible text layer** → reportlab/pikepdf text rendering at `render_mode=3`
   equivalent; validate the text layer is selectable and matches the source.

Until (1)–(3) pass parity, PyMuPDF stays behind the `PdfEngine` boundary, the capabilities endpoint
keeps flagging the AGPL risk, and the license-gate exception remains. **The AGPL blocker is not
claimed resolved until the dependency is actually removed and the license gate passes without the
exception.**

## Consequences

- No fidelity/redaction regression is introduced by a premature swap.
- The remaining work is bounded and explicit (above), each gated by a parity/proof suite.
- `render` and `page-ops/encrypt/compress` are already off AGPL today.

## Progress log

- **2026-06-30** — Two more AGPL touchpoints removed/closed on the
  `expert/packet-audit-and-engine-hardening` branch:
  - **Searchable-PDF permissive path proven.** The reportlab (BSD-3) writer was already
    wired behind `PDF_ENGINE=permissive`; `tests/test_searchable_pdf_permissive.py` now
    proves it emits genuinely selectable text (verified with pypdfium2, not fitz),
    honors redaction (true removal carries through), and stamps `ReportLab` as Producer
    (guarding against silent fallback to the AGPL engine). Decision (3) above is closed.
  - **`provenance/validation.py` no longer imports fitz.** The redaction-proof output
    scan (`_pdf_page_count`, `_output_text`) used to fall back to PyMuPDF; pypdfium2 is a
    pinned core dependency, so the fallback was dead weight and is removed.

- **Remaining blockers for full AGPL removal** (tracked, deliberately deferred): the
  rich-text parse + table detection path (`adapters/pdf.py`, target Docling) and the
  redaction burn-in path (`writers/pdf_writer.py`, target pikepdf content-stream surgery
  with a recoverable-string proof corpus). These are security/fidelity-critical and are
  not attempted in this branch; PyMuPDF stays honestly gated behind the
  `/capabilities` warning and the license-gate exception until each ships with parity green.

