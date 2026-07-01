# PR golden eval automation (Cursor Agents Window)

When Cursor Automations is enabled for this repo:

1. Trigger: pull request opened or updated
2. Steps: `uv sync`, `python evals/golden_documents/run_local.py`, `python evals/golden_packets/run_local.py`
3. Comment gate: fail PR if either script exits non-zero

Until Agents Window is provisioned, `.github/workflows/ci.yml` runs the same evals on push/PR.
