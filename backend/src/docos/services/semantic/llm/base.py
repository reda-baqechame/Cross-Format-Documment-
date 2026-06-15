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


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        *,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        ...
