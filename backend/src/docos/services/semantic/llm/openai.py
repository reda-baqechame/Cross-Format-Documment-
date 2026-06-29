"""OpenAI LLM client — maps the provider-agnostic contract onto Chat Completions + tools."""

from __future__ import annotations

import json

from docos.services.semantic.llm.base import LLMClient, LLMResponse, Message


def _usage(response) -> dict | None:
    """Plain-dict token usage from a Chat Completions response, when reported."""
    u = getattr(response, "usage", None)
    if u is None:
        return None
    out: dict = {}
    for src, dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        val = getattr(u, src, None)
        if isinstance(val, int):
            out[dst] = val
    return out or None


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", tool.get("parameters", {})),
        },
    }


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
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls: list[dict] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments or "{}"),
                    }
                )

        return LLMResponse(
            text=message.content or "", tool_calls=tool_calls, usage=_usage(response)
        )

    async def converse(
        self,
        system: str,
        messages: list[Message],
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Native multi-turn tool use over Chat Completions (assistant tool_calls + tool role)."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        api_messages: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m.get("role")
            if role == "user":
                api_messages.append({"role": "user", "content": m.get("content", "")})
            elif role == "assistant":
                api_messages.append(
                    {
                        "role": "assistant",
                        "content": m.get("content", "") or None,
                        "tool_calls": [
                            {
                                "id": c["id"],
                                "type": "function",
                                "function": {
                                    "name": c["name"],
                                    "arguments": json.dumps(c.get("input", {})),
                                },
                            }
                            for c in m.get("tool_calls", [])
                        ],
                    }
                )
            elif role == "tool":
                for res in m.get("tool_results", []):
                    api_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": res["id"],
                            "content": str(res.get("content", "")),
                        }
                    )

        kwargs: dict = {"model": self.model, "messages": api_messages}
        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        tool_calls: list[dict] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments or "{}"),
                    }
                )
        return LLMResponse(text=msg.content or "", tool_calls=tool_calls, usage=_usage(response))
