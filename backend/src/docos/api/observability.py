"""Production observability: request IDs, structured logging, and a clean error envelope.

Every request gets an ``X-Request-ID`` (honored if the caller/edge sends one, else generated) bound
to a context variable *and* ``request.state`` so logs and error responses can be correlated. Each
request logs one line (method, path, status, duration, request id); unhandled errors log the
traceback and return a ``{"detail", "request_id"}`` envelope that never leaks internals. Logging is
human-readable by default and JSON when ``LOG_FORMAT=json``. An optional Sentry hook activates only
when ``SENTRY_DSN`` is set (import-guarded so the package being absent is a no-op).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from docos.settings import Settings

logger = logging.getLogger("docos")
access_logger = logging.getLogger("docos.access")

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
# Structured extras promoted onto a log line by both formatters.
_EXTRA_KEYS = ("method", "path", "status", "duration_ms")


def get_request_id() -> str:
    return _request_id.get()


def _request_id_of(record: logging.LogRecord) -> str:
    return getattr(record, "request_id", None) or _request_id.get()


class _JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": _request_id_of(record),
        }
        for key in _EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _HumanFormatter(logging.Formatter):
    """Readable dev format; tolerates records that have no ``request_id`` attribute."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id.get()
        return super().format(record)


def configure_logging(settings: Settings) -> None:
    """Install a single stream handler (JSON or human) on the root logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter() if settings.log_format == "json" else _HumanFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id, emit one access log line, and stamp the id on the response."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = rid  # readable by exception handlers (run outside this scope)
        token = _request_id.set(rid)
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": round((time.monotonic() - start) * 1000, 1),
                },
            )
            raise  # let the registered handler build the envelope
        finally:
            _request_id.reset(token)

        access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000, 1),
            },
        )
        response.headers[REQUEST_ID_HEADER] = rid
        return response


def register_error_handlers(app: FastAPI) -> None:
    """Return clean, correlated error envelopes (never leak tracebacks)."""

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "-")
        logger.error("unhandled error", exc_info=exc, extra={"request_id": rid})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "request_id": rid},
            headers={REQUEST_ID_HEADER: rid},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = getattr(request.state, "request_id", "-")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": rid},
            headers={**(exc.headers or {}), REQUEST_ID_HEADER: rid},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = getattr(request.state, "request_id", "-")
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors(), "request_id": rid}),
            headers={REQUEST_ID_HEADER: rid},
        )


def init_sentry(settings: Settings) -> None:
    """Activate Sentry only when SENTRY_DSN is set; a missing package is a no-op."""
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - sentry is an optional extra
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; error tracking is off")
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,  # error tracking only by default; no perf overhead
    )
    logger.info("sentry error tracking enabled (env=%s)", settings.app_env)
