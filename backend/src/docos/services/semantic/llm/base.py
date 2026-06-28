"""``LLMClient`` interface — the only thing the orchestrator depends on.

Keeping the orchestrator vendor-agnostic is what makes the three privacy modes
possible: offline uses a deterministic noop client; enterprise/cloud swap in a
hosted provider without touching orchestration logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    tool_calls: list[dict] = []
    raw: dict | None = None


# A turn in a multi-step tool-calling conversation. Provider-agnostic so the agent loop never
# depends on a vendor's message shape:
#   {"role": "user",      "content": str}
#   {"role": "assistant", "content": str, "tool_calls": [{"id","name","input"}]}
#   {"role": "tool",      "tool_results": [{"id","name","content"}]}
Message = dict


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse: ...

    async def converse(
        self,
        system: str,
        messages: list[Message],
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Continue a multi-turn, tool-calling conversation and return the next assistant turn.

        This is what powers the agentic loop (plan → call tool → observe → repeat). The default
        implementation degrades gracefully to ``complete`` by flattening the transcript into one
        prompt, so any client works; the hosted clients override it with native multi-turn tool use.
        """
        transcript: list[str] = []
        for m in messages:
            role = m.get("role")
            if role == "user":
                transcript.append(f"User: {m.get('content', '')}")
            elif role == "assistant":
                if m.get("content"):
                    transcript.append(f"Assistant: {m['content']}")
                for call in m.get("tool_calls", []):
                    transcript.append(f"Assistant called {call.get('name')}({call.get('input')})")
            elif role == "tool":
                for res in m.get("tool_results", []):
                    transcript.append(f"Tool {res.get('name')} returned: {res.get('content')}")
        return await self.complete(system, "\n".join(transcript), tools=tools)
