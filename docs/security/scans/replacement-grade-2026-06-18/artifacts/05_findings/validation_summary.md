# Validation Summary

Rubric used for each candidate:

- [x] Attacker-controlled source is identified.
- [x] Sink or broken control is identified.
- [x] Realistic product entry point exists.
- [x] Focused code change closes the source-to-sink path.
- [x] Regression test proves the fix or exact suppression evidence is recorded.

| Candidate | Validation Method | Disposition | Evidence |
| --- | --- | --- | --- |
| C1 | Focused unit test | fixed | `test_same_client_cannot_bypass_limit_by_rotating_session` blocks same client after rotating sessions. |
| C2 | Focused unit test | fixed | `test_ooxml_sniffer_does_not_bless_over_entry_cap_archive` returns `application/zip` for over-entry OOXML-like archive. |
| C3 | Integration test | fixed | `test_malformed_magic_matched_file_is_rejected_before_blob_stage` returns 422, records failed job, and leaves no blob. |
| C4 | Unit test | fixed | `test_redacted_field_value_is_removed_and_validation_detects_leak` removes field value and catches synthetic leak. |
| C5 | Unit test | fixed | `test_csv_and_xlsx_escape_spreadsheet_formula_payloads` proves CSV/XLSX do not serialize formulas. |
| C6 | Unit test | fixed | `test_html_and_markdown_drop_unsafe_link_schemes` drops `javascript:` links. |
| C7 | Unit test | fixed | `test_pdf_writeback_strips_active_links_and_javascript` strips links and validates PDF output. |
| C8 | Integration test | fixed | `test_templates_are_session_scoped` blocks cross-session list/instantiate/delete. |

Commands proving validation:

- `python -m pytest backend/tests -q -m "not stress"`: 264 passed, 1 skipped, 6 deselected.
- `python -m pytest backend/tests/stress -q`: 6 passed.
- `python -m ruff check backend/src backend/tests evals`: all checks passed.

