# Scoped Coverage Ledger

| Row | Boundary | Files Checked | Family | Disposition | Evidence |
| --- | --- | --- | --- | --- | --- |
| U1 | Upload and ingestion | `routes_documents.py`, `ratelimit.py`, `session.py`, ingestion gateway/allowlist/scanner | DoS/rate limit | reportable fixed | C1 fixed by session + client-address buckets; regression test added. |
| U2 | OOXML/zip sniffing | `allowlist.py`, `gateway.py` | Zip bomb/pre-validation DoS | reportable fixed | C2 fixed by capped OOXML classifier; regression test added. |
| U3 | Upload parse/stage | `routes_documents.py`, `gateway.py` | Unsafe upload/storage growth | reportable fixed | C3 fixed by parsing before blob staging and 422 parser failure; regression test added. |
| U4 | Document ownership | `access.py`, document-scoped routes | IDOR/BOLA | suppressed | Routes use `_load_latest`, `get_owned_document`, or owner-filtered queries; cross-owner access 404s. |
| U5 | Asset upload | `routes_documents.py` | Unsafe asset upload | suppressed | Asset upload checks ownership, capped read, magic sniff, image MIME allowlist, scanner, generated blob key. |
| E1 | Export redaction | markup/DOCX/PPTX/XLSX/PDF writers, validation | Sensitive data recovery | reportable fixed | C4 fixed by redaction-aware node text and validation over `text`, `value`, `alt_text`. |
| E2 | Spreadsheet export | `markup.py`, `xlsx_writer.py` | Formula injection | reportable fixed | C5 fixed by apostrophe neutralization for CSV/XLSX cells; regression test added. |
| E3 | Link export | `markup.py`, patch link fields | Active link/XSS | reportable fixed | C6 fixed by safe-scheme allowlist; regression test added. |
| E4 | PDF write-back | `pdf_writer.py`, `routes_export.py` | Active PDF content | reportable fixed | C7 fixed by PyMuPDF scrub for links/JavaScript/embedded files; regression test added. |
| E5 | Export authz | `routes_export.py`, `_load_latest` | Cross-document read | suppressed | Export/report/preview load owned document before reading blob/model. |
| W1 | Templates | `routes_templates.py`, `Template` model/migrations | IDOR/BOLA | reportable fixed | C8 fixed by template ownership columns and route filters/checks; regression test added. |
| W2 | Forms | `routes_forms.py` | Cross-document mutation | suppressed | Field routes load owned document before detect/create/update/delete/fill. |
| W3 | Approvals/bulk-send | `routes_approvals.py`, `routes_bulk_send.py` | Unauthorized workflow side effect | suppressed | Source documents are owned; copied packets are assigned to actor session. |
| W4 | Editor sessions | `routes_editor.py`, `services/editor/sessions.py` | Provider SSRF/config injection | suppressed | Provider URLs come only from settings; request provider is a selector, not a URL. Sessions enforce document ownership. |
| W5 | Ops/query/AI | `routes_ops_agent.py`, `routes_query.py`, orchestrator/openai client | Agent/tool safety | suppressed | Plan endpoint is read-only; destructive actions are metadata-only and approval-gated. Query routes load owned docs. |

