"""Anthropic LLM client.

Maps the provider-agnostic ``complete`` contract onto the Messages API with tool
use. Used only when ``LLM_PROVIDER=anthropic``; install with
``pip install -e .[anthropic]``. The ``anthropic`` import is lazy so the module
loads (and the rest of the app runs offline) without the SDK present.
"""

from __future__ import annotations

from docos.services.semantic.llm.base import LLMClient, LLMResponse, Message


def _cacheable_system(system: str) -> list[dict]:
    """The system prompt as a cache-marked block.

    The agent's system prompt is large and constant across every turn of a loop; marking it
    ``ephemeral`` lets Anthropic prompt-caching serve it from cache on each subsequent call, cutting
    cost/latency without changing behaviour.
    """
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def _usage(message) -> dict | None:
    """Plain-dict token usage from an Anthropic message (cache fields included when present)."""
    u = getattr(message, "usage", None)
    if u is None:
        return None
    out: dict = {}
    for field in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        val = getattr(u, field, None)
        if isinstance(val, int):
            out[field] = val
    return out or None


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
            "system": _cacheable_system(system),
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

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, usage=_usage(message))

    async def converse(
        self,
        system: str,
        messages: list[Message],
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Native multi-turn tool use: map the agnostic transcript onto Anthropic content blocks."""
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        api_messages: list[dict] = []
        for m in messages:
            role = m.get("role")
            if role == "user":
                api_messages.append({"role": "user", "content": m.get("content", "")})
            elif role == "assistant":
                content: list[dict] = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for call in m.get("tool_calls", []):
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["name"],
                            "input": call.get("input", {}),
                        }
                    )
                api_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": res["id"],
                        "content": str(res.get("content", "")),
                    }
                    for res in m.get("tool_results", [])
                ]
                api_messages.append({"role": "user", "content": content})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 8192,
            "thinking": {"type": "adaptive"},
            "system": _cacheable_system(system),
            "messages": api_messages,
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
        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, usage=_usage(message))
