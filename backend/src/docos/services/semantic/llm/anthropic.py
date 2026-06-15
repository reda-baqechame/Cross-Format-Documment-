"""Anthropic LLM client.

Maps the provider-agnostic ``complete`` contract onto the Messages API with tool
use. Used only when ``LLM_PROVIDER=anthropic``; install with
``pip install -e .[anthropic]``. The ``anthropic`` import is lazy so the module
loads (and the rest of the app runs offline) without the SDK present.
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
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 8192,
            # Adaptive thinking lets the model reason about the edit before emitting ops;
            # with thinking enabled tool_choice stays "auto" (forced tool use isn't
            # supported alongside thinking), so the system prompt insists on emit_patch.
            "thinking": {"type": "adaptive"},
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if tools:
            kwargs["tools"] = tools

        message = await client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[dict] = []
        for block in message.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)
