# Capability ladder — when a feature may be claimed, marketed, or sold

> The discipline that keeps this product honest. Every capability is graded on the same
> 0–10 ladder; nothing is marketed above the rung it has actually earned.

The `/capabilities` truth ledger already distinguishes `verified`, `degraded`,
`provider_gated`, `disabled`, `broken`, and `claim_without_proof`. This ladder sits **above**
that ledger and answers a harder question: *how much may we say about a capability?*

## The ladder

| Rung | Label | Meaning | What you may say |
|:---:|---|---|---|
| 0 | `idea` | Not built. | Nothing. |
| 1 | `route_exists` | An endpoint exists but returns stub data. | Nothing public. |
| 2 | `toy` | Works on a curated sample file. | "Demo only." |
| 3 | `golden` | Works on a golden-corpus fixture. | "Works on test data." |
| 4 | `messy_real` | Works on a messy real-world file. | "Handles real documents." |
| 5 | `cited` | Every factual output cites document + page + node + raw text. | "Evidence-bound." |
| 6 | `reversible` | Mutations are patch-based, previewable, undoable, audited. | "Safe to act on." |
| 7 | `export_validated` | The exported artifact is opened and checked. | "Send-ready output." |
| 8 | `eval_gated` | A regression in CI fails the build. | "Verified." (matches `/capabilities: verified`) |
| 9 | `expert_verified` | Passes a human-reviewed golden answer key. | "Expert-grade." |
| 10 | `market_superior` | Beats a named competitor on a measured benchmark. | "Better than [tool] at [task]." |

## Rules

1. **No rung may be skipped in a public claim.** You cannot say "expert-grade" (9) if the
   feature is only at rung 5. The `/capabilities` state must agree.
2. **Rung 10 requires a competitor named in `docs/benchmarks/`.** "Better than the market"
   without naming who, and on what measured task, is forbidden.
3. **Absence of evidence is itself a finding.** A feature that detects "X is missing" may
   only do so by escalating to `human_review_required` — it may never assert an unfounded
   blocking claim. (Enforced in `expert/rules.py:new_finding`.)
4. **Provider-gated is not verified.** An LLM-dependent feature that works only with a key
   is `provider_gated`, never `expert_verified`, until its offline deterministic core is
   proven and the LLM is provably grounded in cited evidence.

## Where each capability sits today (2026-06-30)

| Capability | Rung | State in `/capabilities` |
|---|:---:|---|
| Packet audit — import/export vertical | 8 | verified → expert_verified after golden corpus |
| Packet audit — AP vertical | 8 | verified |
| Packet audit — contracts vertical | 8 | verified |
| Packet audit — HR vertical | 8 | verified |
| Packet audit — insurance vertical | 8 | verified |
| True redaction (zero recoverable bytes) | 8 | verified (CI-gated) |
| BM25 search | 8 | verified |
| Owner isolation / rate limiting | 8 | verified |
| PDF page-ops / encrypt / compress (permissive) | 8 | verified |
| Semantic search (embeddings) | 3 | degraded (BM25 fallback) |
| AI ask / summarize / edit | 3 | provider_gated |
| Legal e-signature | 2 | provider_gated (HMAC seal only) |
| Native PDF/Office editing parity | 2 | provider_gated |
| Full AGPL-free PDF parse/redaction | 3 | in progress (ADR-002) |

## The path to rung 9–10

- **Rung 9 (expert_verified):** commit a human-reviewed golden answer key per vertical
  under `evals/golden_packets/<vertical>/` and a scorer that fails CI on regression. Target
  field precision ≥ 95%, critical-finding recall ≥ 98%, evidence coverage = 100%.
- **Rung 10 (market_superior):** run the `docs/benchmarks/packet-audit.md` matrix against a
  real competitor on the same packets and record the measured result.
