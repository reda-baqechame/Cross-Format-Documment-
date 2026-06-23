"""Live presence — who's currently viewing a document (single-node, heartbeat/poll).

A real, dependency-free presence layer: each open view sends a heartbeat and gets back the list of
views active within the TTL window. It works out of the box on the single-service deploy (one
in-process registry). Because documents are private to their owning session, "everyone viewing" is
that session's own open tabs/devices today; cross-person sharing and true co-editing (CRDT) need
collaboration infrastructure — the ``PresenceHub`` interface is the seam where a Redis-backed,
multi-node hub drops in (``COLLAB_BACKEND=redis``).
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

from pydantic import BaseModel


class Viewer(BaseModel):
    viewer_id: str
    name: str
    color: str
    # seconds since this viewer's last heartbeat (0 = just now)
    idle_seconds: float = 0.0


class PresenceHub(ABC):
    @abstractmethod
    def heartbeat(self, doc_id: str, viewer_id: str, name: str, color: str) -> list[Viewer]: ...

    @abstractmethod
    def viewers(self, doc_id: str) -> list[Viewer]: ...

    @abstractmethod
    def leave(self, doc_id: str, viewer_id: str) -> None: ...


class MemoryHub(PresenceHub):
    """Single-node in-process registry with TTL eviction."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        # doc_id -> viewer_id -> (name, color, last_seen_monotonic)
        self._state: dict[str, dict[str, tuple[str, str, float]]] = {}

    def _prune(self, doc_id: str, now: float) -> dict[str, tuple[str, str, float]]:
        views = self._state.get(doc_id, {})
        live = {vid: v for vid, v in views.items() if now - v[2] <= self.ttl}
        if live:
            self._state[doc_id] = live
        else:
            self._state.pop(doc_id, None)
        return live

    def _snapshot(self, views: dict[str, tuple[str, str, float]], now: float) -> list[Viewer]:
        return [
            Viewer(viewer_id=vid, name=name, color=color, idle_seconds=round(now - seen, 1))
            for vid, (name, color, seen) in sorted(views.items())
        ]

    def heartbeat(self, doc_id: str, viewer_id: str, name: str, color: str) -> list[Viewer]:
        now = time.monotonic()
        with self._lock:
            views = self._state.setdefault(doc_id, {})
            views[viewer_id] = (name, color, now)
            live = self._prune(doc_id, now)
            return self._snapshot(live, now)

    def viewers(self, doc_id: str) -> list[Viewer]:
        now = time.monotonic()
        with self._lock:
            return self._snapshot(self._prune(doc_id, now), now)

    def leave(self, doc_id: str, viewer_id: str) -> None:
        with self._lock:
            if doc_id in self._state:
                self._state[doc_id].pop(viewer_id, None)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()
