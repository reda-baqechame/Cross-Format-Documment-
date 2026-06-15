"""OpenAI LLM client — STUB.

Extension point: build an AsyncOpenAI client and map ``complete`` to the chat
completions / responses API with tool calling. Install with ``pip install -e .[openai]``.
"""

from __future__ import annotations

from docos.services.semantic.llm.base import LLMClient, LLMResponse


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str | None, model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("OpenAIClient.complete — wire up the OpenAI SDK")
