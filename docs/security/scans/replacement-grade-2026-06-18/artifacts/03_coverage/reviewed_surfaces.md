# Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Upload/session/rate limit | DoS and quota bypass | Fixed | Session and client-address buckets now both apply. |
| OOXML sniffing | Zip bomb pre-validation | Fixed | Over-entry Office-like packages are no longer blessed by the sniffer. |
| Upload parse/stage | Storage growth and parser failures | Fixed | Parser success is required before blob staging. |
| Document ownership | IDOR/BOLA | Rejected | Document-scoped routes reviewed load through ownership controls. |
| Asset upload | Unsafe asset upload | Rejected | Asset upload validates ownership, MIME, scan, size, and generated blob keys. |
| Export redaction | Sensitive data recovery | Fixed | Field values and image alt text now participate in redaction and validation. |
| Spreadsheet export | Formula injection | Fixed | CSV/XLSX formula-leading text is neutralized. |
| HTML/Markdown export | Active unsafe link schemes | Fixed | Exported links are limited to safe schemes or relative references. |
| PDF write-back | Active PDF links/actions | Fixed | Basic PDF export scrubs links, JavaScript, embedded files, and response actions. |
| Templates | Cross-session IDOR | Fixed | Templates now have owner columns and owner-scoped routes. |
| Forms | Cross-document mutation | No issue found | Routes load owned document before mutation. |
| Approvals/bulk send | Unauthorized workflow side effect | No issue found | Source ownership is enforced and copied packets are session-owned. |
| Editor sessions | Provider URL injection/SSRF | Rejected | Provider URLs are operator settings, not request-controlled. |
| Ops/query/AI | Destructive action safety | No issue found | Planner is read-only and destructive actions are approval metadata only. |
