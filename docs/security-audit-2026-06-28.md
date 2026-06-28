# Security audit — 2026-06-28 (Phase B)

Authorized deep-security pass over the backend attack surface. Scope: multi-tenant IDOR,
sessions/cookies, CSRF/CORS, share tokens & PINs, SSRF, XSS, formula injection, archive bombs,
upload/parser handling, rate limiting, and the OpenAPI surface (fuzzed in CI). Severity uses
CVSS-style bands. Every "mitigated" row links to the enforcing code so the claim is checkable.

## Summary

The codebase was already substantially hardened. The pass found **no open Critical/High** issues.
Two real **Low/Medium** hardening gaps were fixed in this phase (security response headers;
spreadsheet-injection prefix completeness). Everything else is mitigated by existing controls,
verified against the code and the test suite.

## Findings & status

| # | Area | Severity | Status | Evidence / fix |
|---|------|----------|--------|----------------|
| 1 | Missing security response headers (clickjacking, MIME-sniffing, referrer leak) | Medium | **Fixed** | `api/security_headers.py` adds `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cross-Origin-Resource-Policy`, strict `Content-Security-Policy` (docs-exempt), and HSTS in production. Tests: `tests/test_security_headers.py`. |
| 2 | Spreadsheet/CSV formula injection — tab/CR prefixes not neutralised | Low | **Fixed** | `writers/redaction.py::_SPREADSHEET_FORMULA_PREFIXES` now includes `\t` and `\r`; all CSV/XLSX cells route through `spreadsheet_text()`. Test: `test_formula_injection_neutralised_for_all_prefixes`. |
| 3 | Multi-tenant IDOR on documents/assets | High | Mitigated | Centralised `api/access.py::owner_clause` / `get_owned_document` — every doc route filters by `(session_id OR user_id)` and returns **404** (not 403) on non-owned, so existence isn't leaked. |
| 4 | Share-token guessing | Medium | Mitigated | Tokens are `secrets.token_urlsafe(24)` (192-bit); sessions `token_urlsafe(32)`. `access.py::get_valid_share` checks revoked + expiry. |
| 5 | Share-PIN brute force | Medium | Mitigated | PINs stored as bcrypt hashes (`verify_password`); every portal endpoint carries `enforce_portal_rate` (`api/ratelimit.py`), per-client token bucket. |
| 6 | Auth (login/register) brute force | Medium | Mitigated | `enforce_auth_rate` per client address on auth routes. |
| 7 | Session/auth cookies | Medium | Mitigated | `api/session.py`: `HttpOnly`, `SameSite=lax`, `Secure` in production. |
| 8 | CORS misconfiguration | Medium | Mitigated | `main.py` uses an explicit allow-list (`cors_origins`, default `http://localhost:3100`); no `allow_credentials` + `*` combo. |
| 9 | SSRF via outbound fetches | High | Mitigated | All `httpx` calls (tts/esign/integrations/drm/idp/handwriting) target **admin-configured** provider URLs from settings, never user-supplied URLs; all are provider-gated (501 when unset). |
| 10 | Stored XSS via exported links | Medium | Mitigated | `writers/redaction.py::safe_link_href` allow-lists `http/https/mailto/tel`; `nosniff` + strict CSP on responses (finding 1). |
| 11 | Archive/zip bombs (OOXML) | Medium | Mitigated | `ingestion/allowlist.py::inspect_zip_safety` caps entries, uncompressed size, and ratio before parsing. |
| 12 | Malicious uploads (executables, macros, EICAR, PDF launch) | High | Mitigated | `ingestion/scanner.py::ContentDefenseScanner` (Phase A), default-on; `tests/test_scanner_content_defense.py`. |
| 13 | Unhandled-input 500s across the API | Medium | Mitigated | Schemathesis `not_a_server_error` fuzzing in CI (Phase A `security` job); provider-gated 501 seams excluded by design. |
| 14 | Dependency / license supply chain | High | Mitigated | Phase A: pip-audit gate (0 vulns), license gate, SBOM, SHA-pinned actions. |

## Residual / accepted risk

- **Rate-limit buckets are per-worker** (in-process token bucket). Documented in `ratelimit.py`; the
  cloud upgrade is a Redis-backed limiter behind the same dependency. Acceptable for the current
  single-/few-worker deployment; revisit at horizontal scale.
- **PyMuPDF parser RCE surface** — mitigated by the content-defense scanner rejecting `/Launch`
  and embedded executables, but the AGPL parser itself is replaced in Phase C (PdfEngine migration).

## Verification (retest receipts)

- `pytest -m "not stress"` → 472 passed, 1 skipped.
- `tests/test_security_headers.py` → 5 passed (headers present; HSTS absent in dev; docs CSP-exempt;
  formula prefixes neutralised).
- Phase A `security` CI job (pip-audit / license / SBOM / schemathesis) → green on `main`.
