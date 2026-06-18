# Attack Path Analysis

All candidates were in scope for the repository threat model because they affect public document
upload, export, template, or workflow surfaces.

## C1 Upload Rate-Limit Session Rotation

Attack path: unauthenticated client omits or rotates `docos_sid`, receives a fresh signed session,
and bypasses a per-session upload bucket. Impact is parser/storage/scanner DoS amplification.
Severity after policy: medium before fix. Fixed by enforcing both session and client-address
buckets.

## C2 OOXML Sniff Before Entry Cap

Attack path: attacker uploads an OOXML-like archive with excessive entries; classifier blesses it
as an Office file before the authoritative safety check. Impact is pre-rejection CPU/memory
pressure. Severity after policy: medium before fix. Fixed by capping the OOXML classifier.

## C3 Blob Stage Before Parser Success

Attack path: attacker submits malformed accepted-magic bytes; validation/scanning pass, blob is
staged, parser fails, leaving storage growth and a raw failure path. Severity after policy: low to
medium before fix. Fixed by parsing before staging and returning 422 on parser failure.

## C4 Non-Run Redaction Recovery

Attack path: user redacts a field/image/non-run node and exports HTML/DOCX/PPTX/CSV/XLSX while
validation only scans run text. Impact is sensitive data recovery from supposedly validated
exports. Severity after policy: high before fix. Fixed across writers and validation.

## C5 Spreadsheet Formula Injection

Attack path: attacker-controlled document/table text beginning with formula metacharacters is
exported to CSV/XLSX and later opened in spreadsheet software. Impact is external callbacks or data
exfiltration from the opener environment. Severity after policy: medium before fix. Fixed by
neutralizing formula-leading strings.

## C6 Unsafe HTML/Markdown Link Schemes

Attack path: attacker-controlled `link_href` stores `javascript:` or another active scheme; exported
HTML/Markdown contains clickable active links. Impact requires user click/open in a renderer that
honors the scheme. Severity after policy: low to medium before fix. Fixed with safe scheme filtering.

## C7 Active PDF Links/Actions Preserved

Attack path: attacker uploads a PDF with active URI/JavaScript/link objects; basic write-back returns
the original active objects as a trusted export. Severity after policy: medium before fix. Fixed by
scrubbing links, JavaScript, embedded files, and response actions during basic PDF write-back.

## C8 Global Template Library IDOR

Attack path: one anonymous session saves a template; another session lists, instantiates, or deletes
the template because the table had no owner columns and routes did not filter by actor. Impact is
cross-session document/template disclosure and tampering. Severity after policy: high before fix.
Fixed by adding template ownership columns, filtering list, and checking ownership on instantiate and
delete.

No candidate remains reportable after the fixes and regression tests above.

