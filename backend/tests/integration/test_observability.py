"""Observability: request-id propagation + a clean error envelope that never leaks tracebacks."""

from __future__ import annotations

from fastapi.testclient import TestClient

from docos.main import create_app


def _app_with_boom() -> TestClient:
    app = create_app()

    @app.get("/boom")
    def _boom() -> dict:
        raise RuntimeError("kaboom — should not leak to the client")

    # raise_server_exceptions=False so the registered handler builds the 500 response.
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_returns_clean_envelope_with_request_id():
    client = _app_with_boom()
    res = client.get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["detail"] == "Internal server error."  # no traceback / internals leaked
    assert "kaboom" not in res.text
    assert body["request_id"]
    assert res.headers["X-Request-ID"] == body["request_id"]


def test_inbound_request_id_is_echoed():
    client = _app_with_boom()
    res = client.get("/live", headers={"X-Request-ID": "trace-abc-123"})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "trace-abc-123"


def test_generated_request_id_when_absent():
    client = _app_with_boom()
    res = client.get("/live")
    assert res.headers.get("X-Request-ID")  # one was generated
