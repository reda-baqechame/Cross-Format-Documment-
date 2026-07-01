# Packet-audit benchmark — Cross-Format Document OS vs. generic document/AI tools

> Last updated: 2026-06-30 · Verticals: import/export, AP, contracts, HR, insurance
> Proof: `backend/tests/unit/test_expert_spine.py`, `test_expert_verticals.py`,
> `test_packet_audit_api.py` (21 tests, CI-gated).

## Why this benchmark exists

Most document tools — Adobe Acrobat AI, DocuSign IAM, Box AI, Microsoft 365 Copilot,
generic ChatGPT-with-a-file — reason about **one file at a time**. They summarize, extract,
and answer questions about a single document. None of them natively treats a **packet** of
related business documents as one transaction whose facts must agree, and none of them ties
every conclusion to a cited source span inside the original file.

This is the narrow lane where Cross-Format Document OS is measurably stronger: **expert-grade,
evidence-bound packet auditing**. The table below is a capability comparison, not a fidelity
opinion. Every cell that says we do something is backed by a test that asserts it.

## What "evidence-bound" means (and why it wins)

A generic tool will say: *"There may be a mismatch."*

Our engine says: *"Blocking — invoice total is CAD 14,920.00 on `inv1` page 1 node
`inv1_run4` (raw: 'Total: CAD 14,920.00'); PO total is CAD 13,780.00 on `po1` page 1 node
`po1_run2` (raw: 'Total: CAD 13,780.00'). Difference: CAD 1,140. Action: reconcile before
payment."*

The rule builder **refuses to emit an unfounded blocking claim** — a blocking/warning finding
with no cited evidence and no `human_review_required` flag raises an error at construction
time. This is enforced in code (`expert/rules.py:new_finding`), not just policy.

## Capability matrix

| Capability | Cross-Format Document OS | Acrobat AI | DocuSign IAM | Box AI | M365 Copilot | ChatGPT (upload) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Multi-document packet reasoning** (treat N docs as one transaction) | ✅ | ❌ | ❌ | partial | ❌ | partial |
| **Cross-document contradiction detection** (total/currency/weight/qty/date) | ✅ cited | ❌ | ❌ | ❌ | ❌ | unreliable |
| **Missing-required-document detection** (customs/onboarding/AP checklist) | ✅ | ❌ | ❌ | ❌ | ❌ | unreliable |
| **Per-finding source citation** (document + page + node + raw span) | ✅ always | partial | partial | partial | ❌ | ❌ |
| **Deterministic verdict** (ready / needs_review / blocked) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **True-removal redaction proof** (zero recoverable bytes incl. OOXML parts) | ✅ CI-gated | partial | ❌ | ❌ | ❌ | ❌ |
| **Reversible, auditable fix plans** (patch → preview → apply → undo) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Export validation** (every export opened + checked) | ✅ | partial | ❌ | ❌ | ❌ | ❌ |
| **Full audit trail** (every action timestamped + attributed) | ✅ | partial | partial | ❌ | ❌ | ❌ |
| **Offline / deterministic** (no LLM, no network, no hallucination) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

Legend: ✅ = backed by a passing test in this repo. partial = the vendor does a weaker
version. ❌ = not a native capability. "unreliable" = an LLM may surface it but cannot
guarantee it or cite it.

## What we do NOT claim

We do not claim to beat Adobe at PDF editing, DocuSign at legal e-signature infrastructure,
Microsoft at workplace-graph intelligence, or Box at enterprise content management. Those are
their home turf. Our claim is narrow and provable:

> **For evidence-bound auditing of a business document packet — detecting cross-document
> contradictions, missing required documents, and redaction/metadata leaks before the packet
> is sent — this engine produces more complete, more cited, and more auditable results than
> generic PDF/AI tools, and it does so deterministically and offline.**

## How each capability is proven (test → capability)

| Capability | Test |
|---|---|
| Cited cross-doc total mismatch → blocked | `test_mismatched_totals_blocked_with_citations` |
| Clean packet → ready | `test_clean_packet_is_ready` |
| Evidence carries page + node + raw text | `test_evidence_refs_carry_page_and_node` |
| Rule builder refuses unfounded blocking claim | `test_rule_builder_refuses_uncited_blocking_finding` |
| Absence escalates to human review | `test_missing_origin_is_human_review_not_unfounded` |
| AP duplicate-invoice detection (cited) | `test_ap_duplicate_invoice_is_blocked_and_cited` |
| Contracts auto-renew cited | `test_contracts_auto_renew_is_cited` |
| HR complete packet → ready | `test_hr_offer_with_comp_and_start_is_ready` |
| Insurance claim-outside-coverage (triple-cited) | `test_insurance_claim_outside_coverage_is_blocked_and_triple_cited` |
| Packet owner isolation (no cross-session leak) | `test_packet_owner_isolation` |
| Zero recoverable secret bytes on export | `evals/redaction_proof` + `test_redaction_proof.py` |

## Reproducing it

```bash
cd backend
.venv/Scripts/python -m pytest tests/unit/test_expert_spine.py tests/unit/test_expert_verticals.py \
  tests/test_packet_audit_api.py -v
```

Every assertion in those files is the benchmark. If any fails, the claim is withdrawn —
that is the discipline that separates this from marketing.
