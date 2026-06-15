"""Provider-agnostic LLM client. ``LocalNoopClient`` is the offline-mode default."""

from docos.services.semantic.llm.base import LLMClient, LLMResponse
from docos.services.semantic.llm.noop import LocalNoopClient

__all__ = ["LLMClient", "LLMResponse", "LocalNoopClient"]
