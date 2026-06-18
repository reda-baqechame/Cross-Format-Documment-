# Security Review: Cross-Format Document OS replacement-grade hardening

## Scope

- Scan mode: scoped-path/security-surface scan.
- In-scope code: upload/parsing/storage, patch/export/redaction, forms/templates,
  approvals/bulk-send, editor-session APIs, query/AI routes, and the DocumentOpsAgent planner.
- Context: repository threat model generated during this scan and saved at
  `docs/security/threat_model.md`.
- Artifacts: discovery report, coverage ledger, validation summary, attack-path report, and
  per-candidate ledgers under this scan directory.
- Explicit limitation: this was not a dependency advisory scan or a fresh exhaustive frontend audit.

### Scan Summary

| Field | Value |
| --- | --- |
| Reportable findings after fixes | 0 |
| Candidates discovered | 8 |
| Candidates fixed | 8 |
| Validation mode | Focused unit/integration/stress tests plus code tracing |
| Coverage | All scoped hardening rows closed as fixed or suppressed |

## Threat Model

This scan used the generated repository threat model in `docs/security/threat_model.md`.

Important invariants from that threat model:

- A caller can read or mutate only documents and templates owned by their signed anonymous session
  or future authenticated user.
- Upload handling must bound memory, reject unsupported/deceptive file types, and reject zip bombs
  before parser execution.
- Redaction must remove sensitive content from exported bytes, not merely hide it in the UI.
- Patch operations must be validated against the canonical model and remain undoable/auditable.
- Native editor sessions must not claim full Office or Acrobat fidelity unless a real provider is
  configured.
- Integrity seals must not be marketed as legally binding signatures until a regulated provider is
  integrated.
- AI or agent workflows may plan destructive actions, but execution must stay approval-gated.

## Findings

### No Findings

No findings remain reportable after validation and fixes.

The scan found eight candidates and fixed all eight:

| Candidate | Title | Final Outcome |
| --- | --- | --- |
| C1 | Upload rate-limit bypass by rotating anonymous sessions | Fixed and tested |
| C2 | OOXML sniffing before entry-count safety | Fixed and tested |
| C3 | Malformed accepted-format uploads staged before parser success | Fixed and tested |
| C4 | Redaction recovery for non-run field/image text | Fixed and tested |
| C5 | CSV/XLSX formula injection | Fixed and tested |
| C6 | Unsafe HTML/Markdown link schemes | Fixed and tested |
| C7 | Active PDF links/actions preserved in basic write-back | Fixed and tested |
| C8 | Global template library IDOR | Fixed and tested |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct source/configuration/runtime evidence supports the result with no material blocker. |
| medium | Source evidence supports the result, but some deployment behavior would need more proof. |
| low | Weak or incomplete evidence; no final finding in this report uses this label. |

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Upload/session/rate limit | DoS and quota bypass | Fixed | Session and client-address buckets now both apply. |
| OOXML sniffing | Zip bomb pre-validation | Fixed | Over-entry Office-like packages are no longer blessed by the sniffer. |
| Upload parse/stage | Storage growth and parser failures | Fixed | Parser success is required before blob staging. |
| Export redaction | Sensitive data recovery | Fixed | Field values and image alt text now participate in redaction and validation. |
| Spreadsheet export | Formula injection | Fixed | CSV/XLSX formula-leading text is neutralized. |
| HTML/Markdown export | Active unsafe link schemes | Fixed | Exported links are limited to safe schemes or relative references. |
| PDF write-back | Active PDF links/actions | Fixed | Basic PDF export scrubs links, JavaScript, embedded files, and response actions. |
| Templates | Cross-session IDOR | Fixed | Templates now have owner columns and owner-scoped routes. |
| Forms | Cross-document mutation | No issue found | Routes load owned document before mutation. |
| Approvals/bulk send | Unauthorized workflow side effects | No issue found | Source document ownership is enforced and packet copies are session-owned. |
| Editor sessions | Provider URL injection/SSRF | Rejected | Provider URLs are operator settings, not request-controlled. |
| Ops/query/AI | Destructive action safety | No issue found | Planner is read-only; destructive actions remain approval metadata only. |

## Verification

- `python -m pytest backend/tests -q -m "not stress"`: 264 passed, 1 skipped, 6 deselected.
- `python -m pytest backend/tests/stress -q`: 6 passed.
- `python -m ruff check backend/src backend/tests evals`: all checks passed.
- Alembic upgrade/check: head applies through `0007`, no drift.

## Open Questions And Follow Up

- When a native editor provider is connected, run a provider-callback security scan over
  `/documents/{id}/editor/session/{session_id}/sync` and `/save` with the provider's real callback
  authentication model.
- Before marketing legal signing, scan the regulated signing-provider integration for identity,
  certificate, webhook, audit-log, and replay risks.
