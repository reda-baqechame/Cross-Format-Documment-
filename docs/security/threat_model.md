# Cross-Format Document OS Threat Model

## Overview

Cross-Format Document OS is a web application for uploading, parsing, editing, validating,
exporting, and routing business documents. The primary runtime surfaces are the Next.js web
frontend in `apps/web`, the FastAPI backend in `backend/src/docos/api`, document ingestion and
conversion services in `backend/src/docos/services`, SQLAlchemy persistence in
`backend/src/docos/db`, and blob storage implementations in `backend/src/docos/storage`.

The highest-value assets are user-uploaded documents, extracted document data, generated exports,
redaction state, integrity seals, approval routes, template variables, comments, audit events, and
session ownership metadata. The product intentionally supports hostile file inputs such as PDFs,
OOXML zip containers, images, Markdown, CSV, HTML, and RTF, so parser and converter boundaries are
security-critical.

## Threat Model, Trust Boundaries, and Assumptions

The main trust boundaries are browser to web app, web app to backend API, backend to storage,
backend to document parsers/converters, backend to optional AI providers, backend to optional native
editor providers, and backend to future signing or identity providers. Production deployment should
keep the backend private behind the web proxy, and the browser should not receive blob-store
credentials or backend-private URLs.

Attacker-controlled inputs include uploaded document bytes, filenames, declared content types,
document IDs in route paths, patch operation payloads, form field metadata, template variables,
comments, approval route names/emails, document-search text, AI instructions, asset uploads, and
future native-editor sync payloads. Operator-controlled inputs include environment variables,
provider URLs, signing secrets, scanner configuration, storage configuration, and Railway or Docker
service wiring. Developer-controlled inputs include tests, migrations, fixtures, and seed scripts.

Core invariants:

- A caller can read or mutate only documents owned by their signed anonymous session or future
  authenticated user.
- Upload handling must bound memory, reject unsupported or deceptive file types, and reject zip bombs
  before parser execution.
- Redaction must remove sensitive content from exported bytes, not merely hide it in the UI.
- Patch operations must be validated against the canonical model and remain undoable/auditable.
- Native editor sessions must not claim full Office or Acrobat fidelity unless a real provider is
  configured.
- Integrity seals must not be marketed or exposed as legally binding signatures until a regulated
  signing provider is integrated.
- AI or agent workflows may plan destructive actions, but execution must stay approval-gated.

## Attack Surface, Mitigations, and Attacker Stories

The upload surface in `routes_documents.py`, `services/ingestion/gateway.py`, and
`services/ingestion/allowlist.py` is the most exposed. Existing mitigations include capped streamed
reads, declared-size rejection, per-session upload rate limits, magic-byte MIME sniffing, OOXML
package verification by contents, zip central-directory safety checks, and fail-closed scanner
behavior when a real scanner is configured.

The document ownership surface is centralized in `api/access.py` and `api/session.py`. The current
model uses a signed HttpOnly anonymous-session cookie and returns 404 for missing or cross-owner
documents to avoid ID disclosure. Any new document-scoped route must call `_load_latest`,
`get_owned_document`, or `require_owned`.

The mutation surface is `routes_patches.py`, form routes, editor-session routes, approval routes,
template routes, and future provider sync endpoints. Relevant attacker stories include targeting a
different user's document ID, sending patch operations for unknown node IDs, inserting malicious
links or asset references, overwriting template metadata, and using AI instructions to trigger
unapproved destructive operations. Existing controls include node-id validation, versioned commits,
audit events, and explicit approval flags in the DocumentOpsAgent plan.

The export surface is `routes_export.py` and document-engine writers. Relevant attacker stories
include recovering redacted text from exported bytes, exporting malformed documents that bypass
validation, content-disposition filename injection, or producing unsafe HTML/CSV content. Existing
controls include safe filename normalization, validation reports, redaction-aware export checks, and
direct writer boundaries.

The provider boundary includes optional OpenAI/LLM, ONLYOFFICE-compatible editor, external PDF
editor, S3, ClamAV, and future signing providers. Provider URLs and secrets are operator-controlled
and must never be accepted from document content or browser input. Provider callbacks and editor sync
payloads should be authenticated before becoming production mutators.

Out of scope for this repository-level model: compromise of Railway, DNS, browser extensions,
third-party provider internal systems, or a user's local machine after they download a file. Those
risks still matter operationally, but the codebase primarily controls API authorization, file safety,
conversion correctness, and honest product boundaries.

## Severity Calibration

Critical findings include cross-session document read/write, forged session ownership, remote code
execution through file parsing or provider callbacks, leaked storage credentials, or export paths that
recover true-redacted content.

High findings include persistent XSS from document content or comments, SSRF through configurable
provider URLs exposed to attackers, zip-bomb or oversized-file bypass leading to denial of service,
destructive AI/tool execution without approval, or a route that mutates documents without ownership
checks.

Medium findings include incomplete export validation for a supported format, missing audit events on
important mutations, weak rate limits on expensive parsing paths, CSV/HTML formula or script hazards
in generated outputs, and misleading UI labels that overstate PDF editing or legal signing.

Low findings include missing security headers in local development, harmless metadata leakage in
non-production fixtures, non-sensitive verbose error messages, and developer-only tooling issues that
do not affect deployed routes or user documents.
