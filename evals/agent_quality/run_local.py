"""Run the agent-quality eval (Phase E5).

Offline (no provider) it scores the deterministic structural contract and requires 100%. With an
AI provider configured (via the app's settings/env) it runs the iterative loop and requires the
labeled-answer gate (≥95%). Exits non-zero if a gate is missed, so CI can enforce it.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_quality.harness import (  # noqa: E402
    ANSWER_GATE,
    CASES,
    GROUNDING_CASES,
    GROUNDING_GATE,
    STRUCTURAL_GATE,
    aggregate,
    score_grounding,
    score_offline,
    score_with_provider,
)


async def _amain() -> int:
    # Lazy import so the harness path bootstrap (which adds backend/src) runs first.
    from docos.deps import get_llm_client, get_orchestrator  # noqa: E402
    from docos.settings import get_settings  # noqa: E402

    provider = get_settings().effective_llm_provider
    # Each group: (label, gate, cards). Offline always runs structural + grounding gates (both in
    # CI, no key). With a provider, the answer-quality gate runs too.
    groups: list[tuple[str, float, list]] = [
        ("offline structural", STRUCTURAL_GATE, [await score_offline(c) for c in CASES]),
        ("grounding", GROUNDING_GATE, [await score_grounding(c) for c in GROUNDING_CASES]),
    ]
    if provider != "noop":
        llm, orch = get_llm_client(), get_orchestrator()
        provider_cards = [await score_with_provider(c, llm, orch) for c in CASES]
        groups.append((f"provider={provider}", ANSWER_GATE, provider_cards))

    failed = False
    for label, gate, cards in groups:
        passed, total = aggregate(cards)
        rate = (passed / total) if total else 1.0
        for card in cards:
            flag = "ok " if card.passed else "FAIL"
            fails = [k for k, v in card.checks.items() if not v]
            print(f"  [{flag}] ({label}) {card.name}" + (f"  missing: {fails}" if fails else ""))
        verdict = "PASS" if rate >= gate else "FAIL"
        print(
            f"Agent-quality [{label}]: {passed}/{total} = {rate:.0%} "
            f"(gate {gate:.0%}) -> {verdict}"
        )
        failed = failed or rate < gate

    if failed:
        print("GATE FAILED")
        return 1
    print("GATE PASSED")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
