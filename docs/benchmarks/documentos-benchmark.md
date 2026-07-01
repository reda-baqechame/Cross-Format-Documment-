# DocumentOS benchmark score sheet (rung 10)

Manual competitor pass template. Each row compares one golden case across tools.

| Case | DocumentOS verdict | Evidence | Export opens | Minutes | Acrobat | Copilot | ChatGPT | Notes |
|------|-------------------|----------|--------------|---------|---------|---------|---------|-------|
| `case_clean_memo` | ✅ | ✅ | ✅ | 2 | — | — | — | Baseline |
| `import_export/case_mismatch` | ✅ | ✅ | ✅ | 5 | — | — | — | Packet audit |

Generate a new row:

```bash
node scripts/competitor-benchmark.mjs --case evals/golden_documents/case_clean_memo
```

Commit filled rows under `evals/benchmarks/*.json`.

## CI quality floors (L2 evals)

| Metric | Floor | Enforced in |
|--------|-------|-------------|
| Verdict recall | ≥ 98% | `evals/golden_packets/run_local.py` |
| Finding precision | ≥ 95% | `evals/golden_packets/run_local.py` |
| Evidence on warnings/blockers | 100% | both golden runners |
| Export artifact opens | 100% | manual + E2E smoke |
