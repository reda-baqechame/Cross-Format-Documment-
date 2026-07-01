# 500× Master Plan — DocumentOS execution blueprint

> **Vision (unchanged):** The go-to operating system for anything document — open, understand,
> modify, verify, redact, convert, automate, sign, and use AI across every business format.
>
> **Strategy (how we win):** One universal engine (canonical model + evidence + patches + proof)
> plus expert workflow packs. We do not clone Adobe feature-by-feature; we remove document
> bottlenecks end-to-end with measurable outcomes.
>
> **Ground truth:** Post-merge `main` @ PR #79 — expert spine, Command Center, fix plans, clean
> export, golden evals, readiness bridge. See [`implementation-status.md`](implementation-status.md)
> and [`capability-ladder.md`](capability-ladder.md).

---

## 1. Honest audit — what is real today

### Delivers real, provable results (sell with confidence)

| Outcome | Where it lives | Proof |
|---|---|---|
| Upload → parse → canonical model | `services/ingestion`, `services/docengine` | Integration tests, CI |
| Reversible edits (patch → undo/redo) | `services/semantic/orchestrator`, `api/routes_patches.py` | `test_patches`, stress suite |
| True redaction (zero recoverable bytes) | `services/docengine/writers/redaction.py` | `evals/redaction_proof` |
| Export + validation headers | `api/routes_export.py`, `services/provenance/validation.py` | Export integration tests |
| Clean Before Send (single doc) | `services/provenance/readiness.py`, `POST /documents/{id}/clean` | Readiness tests + panel |
| Expert packet audit (5 verticals) | `services/expert/`, `api/routes_packet_audit.py` | `evals/packet_audit`, `evals/golden_packets` |
| Cited findings + deterministic verdict | `expert/evidence.py`, `expert/rules.py`, `expert/report.py` | `tests/unit/test_expert_spine.py` |
| Reversible fix plans (metadata + cited redact) | `expert/fixes.py`, `/packets/{id}/fixes/*` | `test_packet_audit_api.py` |
| Clean packet ZIP export | `/packets/{id}/export` | Same |
| Capability truth ledger | `GET /capabilities` | `tests/test_capabilities.py` |
| BM25 library search | `services/semantic/corpus.py` | Retrieval benchmark CI |
| PDF page-ops (permissive engine) | `services/docengine/pdfengine/` | Parity tests |

### Built but not yet “500×” (partial / gated)

| Area | Reality | Blocker to rung 10 |
|---|---|---|
| AI ask / edit / summarize | Works with provider; offline = noop / degraded | Grounding eval + patch planner UX |
| Semantic search (embeddings) | BM25 fallback; embeddings optional | Recall benchmark on real corpus |
| Legal e-sign | HMAC seal only; provider-gated | External PKI infra |
| Native PDF/Office editing | Basic write-back; external editor seam | Provider + fidelity parity |
| Full AGPL-free PDF parse | ADR-002 in progress | PdfEngine migration |
| Golden packet corpus | 20 cases (≥3/vertical, PDF fixtures) | Messy-real scanned PDFs + competitor runs |
| Competitor benchmark | Matrix doc exists; no measured competitor runs | Rung 10 requires recorded runs |
| Single-doc ↔ packet unification | Shared expert UI + `ResultContract` | DocumentOps Autopilot (Phase 3) |

### Not real enough to claim without qualification

- “Replace Adobe / DocuSign / Microsoft everywhere”
- “Expert-grade on every document type” (only packet verticals + readiness are eval-gated)
- “One-click fixes for every finding” (metadata scrub + cited redaction only)
- “Legal e-signature compliance” without a regulated provider

---

## 2. Product identity — stay broad, execute narrow

**Public promise (empire):**

> DocumentOS — the AI command center for business documents.  
> Ask anything. Modify safely. Verify before you send. Export with proof.

**Five user modes (everything document fits here):**

| Mode | User question | Platform answer |
|---|---|---|
| **Understand** | What is this? What matters? What's missing? | Cited summary, extracted facts, classification |
| **Modify** | Fix this clause / table / page / field | Patch plan → preview → apply → undo |
| **Verify** | Is this safe to send? | Readiness verdict + evidence + proof report |
| **Convert** | Give me a clean PDF/DOCX/XLSX | Export + validation headers |
| **Automate** | Do this for 50 files | Recipes, packs, bulk-send, API |

**Monetization wedge (first dollars):**

1. **Clean Before Send** — universal, every doc type
2. **Expert Packet Audit** — multi-doc contradictions (already strongest)
3. **Contract / AP packs** — deepen vertical rules on the same spine

---

## 3. Architecture — seven layers mapped to this repo

```
┌─────────────────────────────────────────────────────────────┐
│ 7. Automation    recipes · workflows · bulk-send · API      │
├─────────────────────────────────────────────────────────────┤
│ 6. Expert packs  import/export · AP · contracts · HR · …   │
├─────────────────────────────────────────────────────────────┤
│ 5. Verification  readiness · redaction proof · validation   │
├─────────────────────────────────────────────────────────────┤
│ 4. Intelligence  classify · extract · ask · compare · agent │
├─────────────────────────────────────────────────────────────┤
│ 3. Modification  reversible patches · page/table/image ops  │
├─────────────────────────────────────────────────────────────┤
│ 2. Canonical     node graph · DocumentMeta · provenance     │
├─────────────────────────────────────────────────────────────┤
│ 1. Format        adapters · OCR · ingest · blob storage     │
└─────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │         EXPERT SPINE           │
         │  evidence → facts → rules →   │
         │  report → fixes → export      │
         └──────────────────────────────┘
              (services/expert/*)
```

| Layer | Primary paths | Status |
|---|---|---|
| Format | `services/docengine/adapters/*`, `services/ocr/` | ✅ broad; PDF AGPL risk |
| Canonical | `model/document.py`, `model/nodes.py`, `model/patch.py` | ✅ core moat |
| Modification | `services/semantic/orchestrator.py`, `api/routes_patches.py` | ✅ rung 6 |
| Intelligence | `services/semantic/*`, `services/semantic/skills/` | 🟡 provider-gated AI |
| Verification | `services/provenance/*`, `expert/trust.py` | ✅ rung 7–8 |
| Expert packs | `services/expert/verticals/*`, legacy `services/packs/` | ✅ packet verticals |
| Automation | `services/workflows/`, `routes_recipes.py`, `routes_bulk_send.py` | 🟡 recipes partial |

**Invariant (never break):** All mutations → `ReversiblePatch` → `apply` → `commit_version` →
`record_event`. All factual claims → `EvidenceRef` or `human_review_required`.

---

## 4. The 500× formula (what competitors split apart)

```
500× = Canonical model
     + Evidence-bound reasoning
     + Deterministic rules (offline core)
     + LLM judgment (optional, cited only)
     + Reversible fixes
     + Redaction proof
     + Export validation
     + Golden evals (CI gates)
     + Public benchmarks (named competitors)
     + Vertical workflow packaging
     + Correction → test feedback loop
```

You already have the first eight for packet audit. The gap to “feel 500×” is **UX unification**
and **rung 10 competitor measurements**, not more random routes.

---

## 5. Bottleneck removal map → build order

| Bottleneck | Remove with | Phase |
|---|---|---|
| “I don't know what's wrong” | Readiness + expert findings + cited evidence | P0 ✅ / deepen P1 |
| “AI might hallucinate” | Anti-hallucination guard + grounding eval | P1 |
| “Editing breaks the file” | Patch preview + undo + export validation | P0 ✅ |
| “Redaction isn't real” | True removal + un-redact test + proof report | P0 ✅ |
| “Multi-doc contradictions” | Packet Command Center + 5 verticals | P0 ✅ |
| “Fixing is manual” | Fix plans (metadata + redact) → expand rules | P1 |
| “No proof for client/boss” | HTML/PDF proof reports (readiness + packet) | P1 |
| “Repeating same job” | Recipes + pack templates | P2 |
| “50 files at once” | Batch packet audit + bulk clean | P2 |
| “Trust the marketing” | `/capabilities` + capability ladder | P0 ✅ |

---

## 6. Execution phases

### Phase 0 — Shipped (PR #79, do not regress)

- Expert spine: `services/expert/{evidence,fact_graph,rules,report,fixes,trust}.py`
- Packet API + DB: `api/routes_packet_audit.py`, migration `0014_packet_audit.py`
- Command Center UI: `apps/web/src/app/packets/`, `PacketWorkspace.tsx`
- Fixes + clean export + HTML report
- L1 + L2 evals: `evals/packet_audit/`, `evals/golden_packets/`
- Readiness → `ExpertFinding` bridge: `expert/readiness_bridge.py`
- Docs: `capability-ladder.md`, `benchmarks/packet-audit.md`

**Gate:** All CI jobs green on `main`; `pack_audit` = `expert_verified`.

---

### Phase 1 — Universal Command Center (30 days)

**Goal:** One surface for single-doc *and* multi-doc jobs. User never wonders “packet vs workspace.”

| Work item | Action | Files |
|---|---|---|
| Unified entry | Home + nav: “Verify document” → readiness; “Audit packet” → `/packets` | `app/page.tsx`, `AppShell.tsx` |
| Single-doc expert UX | Readiness panel shows findings like Command Center Issues tab | `ReadinessPanel.tsx` |
| Proof report download | `GET /documents/{id}/readiness/report?format=html` mirror packet HTML | `readiness_html.py`, `routes_readiness.py` |
| AI action loop | Promote patch plan preview as default edit path (not raw apply) | `AiEditBar`, `routes_patches.py` |
| Grounding gate (offline) | Ask/summarize return `human_review_required` when no evidence | `reader.py`, query tests |
| Expand fix plans | Date normalization, missing signature block placeholder | `expert/fixes.py`, vertical rules |

**Definition of done**

- [x] Clean Before Send HTML report downloadable
- [x] Readiness findings visually match packet Issues (same components)
- [x] Offline ask/summarize never assert facts without citations
- [x] Playwright: single-doc clean-before-send happy path
- [x] `ResultContract` on readiness + packet report APIs
- [x] `evals/golden_documents/` + expanded `evals/golden_packets/` in CI

---

### Phase 2 — Golden corpus + messy-real (45 days)

**Goal:** Earn rung 9 broadly; stop relying on synthetic TXT-only fixtures.

| Work item | Target |
|---|---|
| Golden packets | ≥3 reviewed cases per vertical under `evals/golden_packets/` |
| Messy-real layer | Add scanned PDF + rotated page cases (OCR path) |
| Document golden set | `evals/golden_documents/` for Clean Before Send (metadata leak, redaction fail, missing date) |
| Competitor harness | `scripts/competitor-benchmark.mjs` — same inputs, score our output vs manual checklist |
| Capability sync | `/capabilities` per-pack states match corpus coverage |

**CI gates (extend existing)**

| Metric | Floor |
|---|---|
| Critical finding recall | ≥ 98% |
| Critical finding precision | ≥ 95% |
| Evidence coverage (blocking/warning) | 100% |
| Redaction recoverability | 0 bytes |
| Export open rate | 100% |

---

### Phase 3 — DocumentOps Autopilot (60 days)

**Goal:** User states an outcome; system runs Understand → Verify → Fix → Export → Proof.

| Workflow | Input | Output |
|---|---|---|
| Clean Before Send | Any single doc | Verdict + fixes + clean export + proof |
| Ask → Fix → Export | NL instruction | Patch plan + preview + validated export |
| Packet audit | N docs | Expert report + fix plans + ZIP |
| Compare & verify | 2+ versions | Diff + contradiction findings |

**Backend additions (extend, don't duplicate)**

```
services/expert/
  autopilot.py      # orchestrates: classify → audit/readiness → plan fixes → export
  result_contract.py  # unified ResultContract schema for all job types
```

**Routes**

```
POST /documents/{id}/autopilot/run     # outcome: clean | review | export
POST /documents/{id}/autopilot/apply   # approved fixes only
GET  /documents/{id}/proof-report      # HTML/PDF proof artifact
```

**Frontend:** `DocumentCommandCenter` — five tabs: Ask | Edit | Verify | Export | Automate

---

### Phase 4 — Automation + feedback loop (90 days)

| Work item | Purpose |
|---|---|
| Human review queue | Accept/reject findings → new golden cases |
| Recipe builder UI | Save Clean Before Send / packet audit as reusable recipe |
| Batch jobs | `POST /jobs/batch-clean`, `POST /jobs/batch-audit` |
| Correction capture | `PATCH /findings/{id}/review` → feeds eval corpus |
| Rung 10 benchmark | Publish measured rows in `docs/benchmarks/documentos-benchmark.md` |

---

## 7. Feature doctrine — five questions before every PR

1. **What bottleneck does this remove?**
2. **What professional result does the user receive?** (not “a new endpoint”)
3. **What proof confirms it worked?** (test, eval, validation header)
4. **What benchmark measures it?**
5. **What export does the user take away?** (file, report, audit trail)

If a PR cannot answer all five, defer it.

---

## 8. Result contract (unify all job outputs)

Every serious job returns the same shape (extend `ExpertReport` / `ReadinessReport`):

```typescript
type ResultContract = {
  job_type: "clean_before_send" | "packet_audit" | "patch_apply" | "export";
  verdict: "ready" | "needs_review" | "blocked";
  score: number;                    // 0–100 readiness
  blocking_count: number;
  warning_count: number;
  findings: ExpertFinding[];      // always evidence-bound
  fix_plans_available: number;
  clean_export_available: boolean;
  proof_report_url?: string;
  human_review_required: boolean;
  audit_event_ids: string[];
};
```

Implement in `services/expert/schemas.py` + expose on readiness and packet routes.

---

## 9. What we claim publicly (and what we don't)

### Safe to claim today

- Evidence-bound multi-document packet audit across import/export, AP, contracts, HR, insurance
- Deterministic verdict + cited findings (offline, no LLM required)
- Reversible metadata scrub and cited redaction fixes on packets
- Clean packet export with validation headers
- True redaction proof on export path (CI-gated)
- Capability truth ledger — no feature marketed above its proof

### Claim only after Phase 2–4

- “Expert-grade on any document type” → needs `evals/golden_documents/`
- “Better than [Adobe|Copilot|Box] at [task]” → needs rung 10 matrix with recorded scores
- “Fully automated document ops” → needs autopilot + batch + recipe proof

---

## 10. Immediate next 14 days (concrete tasks)

| # | Task | Owner lane |
|---|---|---|
| 1 | Unify Readiness + Packet finding UI components | Web |
| 2 | HTML proof report for single-doc readiness | Backend + Web |
| 3 | Add 2 golden cases per vertical (PDF scans) | Evals |
| 4 | Expand `fixes.py` for top 3 readiness auto-fixes | Expert |
| 5 | Offline grounding gate on `/query` routes | Semantic |
| 6 | `DocumentCommandCenter` shell on `/documents/[id]` | Web |
| 7 | Playwright: clean-before-send + fix apply | E2E |
| 8 | Update `architecture.md` stale “stubs only” line | Docs |
| 9 | Production packet smoke script (`/packets` create → audit) | Scripts |
| 10 | Competitor benchmark template (manual score sheet) | Docs |

---

## 11. Success metrics (business-grade)

| Metric | Target |
|---|---|
| Time to first verdict (upload → blocked/ready) | < 30s p95 |
| Critical issue recall (golden) | ≥ 98% |
| False blocking rate (golden) | ≤ 2% |
| Export validation pass rate | 100% |
| Redaction recoverability | 0 |
| User actions to clean send (median) | ≤ 3 clicks |
| Weekly new golden cases from corrections | ≥ 2 |

---

## 12. Related docs

| Doc | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Five-service layout |
| [`canonical-model.md`](canonical-model.md) | Node taxonomy |
| [`implementation-status.md`](implementation-status.md) | Feature checklist |
| [`capability-ladder.md`](capability-ladder.md) | Rung discipline |
| [`benchmarks/packet-audit.md`](benchmarks/packet-audit.md) | Competitor matrix (packet lane) |
| [`roadmap-100x.md`](roadmap-100x.md) | Engine/seam hardening |
| [`adr-002-pdf-engine-migration.md`](adr-002-pdf-engine-migration.md) | AGPL exit plan |

---

**North star:** A user uploads messy documents and receives a **decision-ready, proof-backed,
client-sendable result** — faster and more reliably than a human team with Adobe + email + spreadsheets.

That is DocumentOS. Build the engine once; win vertical by vertical with evidence, not hype.
