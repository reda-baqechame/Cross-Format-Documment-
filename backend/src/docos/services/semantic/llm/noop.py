"""Deterministic offline LLM client.

Returns a canned, structure-safe response so the semantic endpoint is fully
exercisable offline and in tests, with no external calls or data egress.
"""

from __future__ import annotations

from docos.services.semantic.llm.base import LLMClient, LLMResponse


class LocalNoopClient(LLMClient):
    async def complete(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            text=(
                "[offline noop] No edits were generated. Configure LLM_PROVIDER=openai or "
                "anthropic to enable semantic editing."
            ),
            tool_calls=[],
        )
