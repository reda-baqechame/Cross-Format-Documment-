"""Anthropic LLM client — STUB.

Extension point: build an AsyncAnthropic client and map ``complete`` to the Messages
API with tool use. Install with ``pip install -e .[anthropic]``.
"""

from __future__ import annotations

from docos.services.semantic.llm.base import LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str | None, model: str = "claude-opus-4-8") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("AnthropicClient.complete — wire up the Anthropic SDK")
