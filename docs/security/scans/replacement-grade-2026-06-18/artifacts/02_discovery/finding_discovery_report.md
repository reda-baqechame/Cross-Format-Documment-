# Finding Discovery Report

Scope: replacement-grade document hardening surfaces in the FastAPI backend and export writers.

Subagent coverage:

- Upload/auth/storage shard completed with findings C1-C3 and closed rows for owner isolation,
  signed sessions, scanner failure mode, asset MIME validation, blob credential leakage, and
  storage traversal for generated blob keys.
- Patch/export/redaction shard completed with findings C4-C7 and closed rows for document-scoped
  patch/export authz, filename/header injection, signing HMAC, and PPTX-specific active-content
  hazards.
- Editor/forms/templates/agent/query shard was completed by the parent agent after the delegated
  agent did not finish. It produced finding C8 and closed editor provider SSRF/config injection,
  ops-agent destructive-action gating, query route ownership, form field ownership, approval
  ownership, and bulk-send source ownership.

Raw candidates promoted to validation:

- C1: Upload rate-limit bypass by rotating anonymous sessions.
- C2: OOXML sniffer blessed over-entry archives before zip-entry rejection.
- C3: Malformed magic-matched uploads were staged before parser success.
- C4: Redaction bypass for field/image/non-run text with validation blind spot.
- C5: CSV/XLSX formula injection in exported spreadsheet cells.
- C6: Unsafe HTML/Markdown link schemes in exported links.
- C7: Basic PDF write-back preserved active PDF links/actions.
- C8: Templates were globally listable/instantiable/deletable across sessions.

No unfixed candidate remains open after validation.

