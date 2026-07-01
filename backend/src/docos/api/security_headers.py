"""Security response headers.

Applies defence-in-depth headers to every response: MIME-sniffing protection, clickjacking
protection, referrer minimisation, a tight permissions policy, and HSTS in production. A strict
Content-Security-Policy is applied to API/file responses; the interactive docs (Swagger/ReDoc and
the OpenAPI document) are exempted from CSP so they keep working in non-production environments
where they are served.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# These paths render or fetch their own inline assets; a strict CSP would break Swagger/ReDoc.
# They are only served when not in production (see main.create_app), so exempting them is safe.
_CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")

# API and downloaded files are never a trusted HTML origin: lock everything down.
_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, hsts: bool = False) -> None:
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in _BASE_HEADERS.items():
            response.headers.setdefault(name, value)
        if not request.url.path.startswith(_CSP_EXEMPT_PREFIXES):
            response.headers.setdefault("Content-Security-Policy", _STRICT_CSP)
        if self._hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
