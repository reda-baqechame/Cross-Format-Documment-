"""Anonymous session + authenticated user identity.

Every browser gets a signed ``docos_sid`` cookie. Registered users also receive a signed
``docos_uid`` cookie after login/register so ``Actor.user_id`` is populated.
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

SESSION_COOKIE = "docos_sid"
AUTH_COOKIE = "docos_uid"
COOKIE_NAME = SESSION_COOKIE  # backward-compatible alias for tests
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # one year


@dataclass(frozen=True)
class Actor:
    """Who is making the request."""

    session_id: str
    user_id: str | None = None


def mint_session_id() -> str:
    return secrets.token_urlsafe(32)


def sign_value(value: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{mac}"


def unsign_value(token: str, secret: str) -> str | None:
    raw, _, mac = token.partition(".")
    if not raw or not mac:
        return None
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw if hmac.compare_digest(mac, expected) else None


sign_session = sign_value
unsign_session = unsign_value
sign_user = sign_value
unsign_user = unsign_value


class SessionMiddleware(BaseHTTPMiddleware):
    """Validate/issue session + auth cookies and expose ids on ``request.state``."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        secret = settings.signing_secret

        token = request.cookies.get(SESSION_COOKIE)
        session_id = unsign_session(token, secret) if token else None
        issued_session = session_id is None
        if session_id is None:
            session_id = mint_session_id()
        request.state.session_id = session_id

        auth_token = request.cookies.get(AUTH_COOKIE)
        user_id = unsign_user(auth_token, secret) if auth_token else None
        request.state.user_id = user_id

        response = await call_next(request)

        if issued_session:
            response.set_cookie(
                SESSION_COOKIE,
                sign_session(session_id, secret),
                max_age=_COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=settings.is_production,
                path="/",
            )
        return response


def get_actor(request: Request) -> Actor:
    session_id = getattr(request.state, "session_id", None)
    if session_id is None:
        session_id = mint_session_id()
        request.state.session_id = session_id
    user_id = getattr(request.state, "user_id", None)
    return Actor(session_id=session_id, user_id=user_id)


def set_auth_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        AUTH_COOKIE,
        sign_user(user_id, settings.signing_secret),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(AUTH_COOKIE, path="/", secure=settings.is_production)
