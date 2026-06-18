"""Anonymous session identity — the basis for per-visitor document ownership.

Every browser gets a cryptographically random, server-signed session id on first contact,
stored in an HttpOnly cookie. That id *owns* the documents created during the session, so
"no account required" still gives each visitor a private workspace instead of a shared,
world-readable pile. Signing is a stdlib HMAC over ``settings.signing_secret`` (no extra
dependency); a tampered or forged cookie fails verification and a fresh session is minted.

Future auth seam: a registered user can later *claim* their anonymous session's documents
via ``Document.owner_user_id`` (see :mod:`docos.api.access`).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from docos.settings import get_settings

COOKIE_NAME = "docos_sid"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # one year


@dataclass(frozen=True)
class Actor:
    """Who is making the request. ``user_id`` is the future authenticated-user seam."""

    session_id: str
    user_id: str | None = None


def mint_session_id() -> str:
    return secrets.token_urlsafe(32)


def sign_session(session_id: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{mac}"


def unsign_session(token: str, secret: str) -> str | None:
    """Return the session id if the signature is valid, else ``None``."""
    raw, _, mac = token.partition(".")
    if not raw or not mac:
        return None
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw if hmac.compare_digest(mac, expected) else None


class SessionMiddleware(BaseHTTPMiddleware):
    """Validate/issue the anonymous session cookie and expose it on ``request.state``."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        secret = settings.signing_secret
        token = request.cookies.get(COOKIE_NAME)
        session_id = unsign_session(token, secret) if token else None
        issued = session_id is None
        if session_id is None:
            session_id = mint_session_id()
        request.state.session_id = session_id

        response = await call_next(request)

        if issued:
            response.set_cookie(
                COOKIE_NAME,
                sign_session(session_id, secret),
                max_age=_COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
                path="/",
            )
        return response


def get_actor(request: Request) -> Actor:
    """FastAPI dependency: the current request's actor.

    The middleware guarantees ``request.state.session_id`` is set; the fallback only guards
    against the dependency being used without the middleware (e.g. in a misconfigured test).
    """
    session_id = getattr(request.state, "session_id", None)
    if session_id is None:
        session_id = mint_session_id()
        request.state.session_id = session_id
    return Actor(session_id=session_id)
