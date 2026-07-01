# Correction capture → golden corpus

Human finding reviews are stored under `evals/corrections/` via:

`PATCH /documents/{doc_id}/findings/{finding_id}/review`

Weekly target: promote ≥2 accepted corrections into new `evals/golden_documents/case_*` or `evals/golden_packets/*/case_*` fixtures with `expected/verdict.json`.
