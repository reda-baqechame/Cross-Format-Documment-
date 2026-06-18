# DocumentOpsAgent evals

These local evals check the deterministic workflow layer that will sit behind an
OpenAI-powered document operations agent. They intentionally do not call a model:
the goal is to lock down tool routing, approval gates, and legal-signing honesty
before adding probabilistic planning.

Run from the repo root:

```bash
python evals/document_ops/run_local.py
```

The cases cover:

- workflow correctness for form/template/packet goals
- destructive action gating for redaction
- refusal boundary for legal e-sign claims
- citation/tool-plan quality by requiring explicit action reasons

