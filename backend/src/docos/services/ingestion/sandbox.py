"""Sandbox abstraction for running untrusted conversion/parsing work.

``SubprocessSandbox`` is a thin dev implementation. Production extension points:
gVisor, Docker-in-Docker, or Firecracker microVMs with strict resource limits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class Sandbox(ABC):
    @abstractmethod
    async def run(self, fn: Callable[..., Any], *args: Any, timeout_s: int = 30, mem_mb: int = 512) -> Any:
        ...


class SubprocessSandbox(Sandbox):
    """Dev impl: runs in-process. Replace with a true isolation boundary in prod.

    Kept intentionally minimal so the seam is obvious; calling code already treats
    parsing as if it were sandboxed.
    """

    async def run(self, fn: Callable[..., Any], *args: Any, timeout_s: int = 30, mem_mb: int = 512) -> Any:
        # Extension point: spawn an isolated subprocess/microVM with rlimits.
        return fn(*args)
