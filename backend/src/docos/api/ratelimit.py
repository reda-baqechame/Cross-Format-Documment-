"""In-process token-bucket rate limiting (offline-first, zero infra).

A simple per-key token bucket held in process memory. This is deliberately dependency-free
so the offline build needs no Redis; the trade-off is that buckets are per-worker, not shared
across a multi-worker deployment. The cloud-mode upgrade is a Redis-backed limiter behind the
same :func:`enforce_upload_rate` dependency.
"""

from __future__ import annotations

import threading
import time

from fastapi import Depends, HTTPException, Request

from docos.api.session import Actor, get_actor
from docos.settings import get_settings

_lock = threading.Lock()
_state: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_monotonic_ts)


def _allow(key: str, rate_per_min: int, burst: int) -> bool:
    now = time.monotonic()
    refill_per_sec = rate_per_min / 60.0
    with _lock:
        tokens, last = _state.get(key, (float(burst), now))
        tokens = min(float(burst), tokens + (now - last) * refill_per_sec)
        if tokens < 1.0:
            _state[key] = (tokens, now)
            return False
        _state[key] = (tokens - 1.0, now)
        return True


def reset() -> None:
    """Clear all buckets (test helper)."""
    with _lock:
        _state.clear()


def enforce_upload_rate(request: Request, actor: Actor = Depends(get_actor)) -> None:
    """Dependency: throttle uploads per session (falling back to client IP)."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    key = actor.session_id or (request.client.host if request.client else "anon")
    rate = settings.rate_limit_uploads_per_min
    if not _allow(f"upload:{key}", rate, burst=max(rate, 1)):
        raise HTTPException(status_code=429, detail="too many uploads — please slow down")
