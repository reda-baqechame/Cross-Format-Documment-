"""Agent-quality eval — the offline structural gate runs in CI (Phase E5).

Verifies the labeled cases against the deterministic agent contract: the right tools are selected,
edits are proposed (never committed), and review/PII intents pull in the right tool. The answer-
quality gate (≥95%) runs via evals/agent_quality/run_local.py once a provider key is configured.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EVALS = Path(__file__).resolve().parents[2] / "evals"
sys.path.insert(0, str(_EVALS))

from agent_quality.harness import (  # noqa: E402
    CASES,
    STRUCTURAL_GATE,
    aggregate,
    score_offline,
)


async def test_offline_structural_gate_is_fully_green():
    cards = [await score_offline(c) for c in CASES]
    passed, total = aggregate(cards)
    failures = {c.name: [k for k, v in c.checks.items() if not v] for c in cards if not c.passed}
    assert (passed / total) >= STRUCTURAL_GATE, f"structural failures: {failures}"


async def test_every_case_proposes_nothing_committed():
    # The agent must never mutate the document during evaluation (no_commit holds for all cases).
    for case in CASES:
        card = await score_offline(case)
        assert card.checks.get("no_commit") is True, case.name


def test_case_set_is_meaningful():
    # Guard against an empty/degenerate suite silently "passing".
    assert len(CASES) >= 5
    assert any(c.expect_proposal for c in CASES)
    assert any(c.expect_abstain for c in CASES)
    assert any(c.citation_required for c in CASES)
