"""Security response headers + spreadsheet-injection completeness (Phase B hardening)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from docos.main import create_app
from docos.services.docengine.writers.redaction import spreadsheet_text


def test_security_headers_present_on_api_responses():
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "Content-Security-Policy" in r.headers
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_hsts_absent_outside_production():
    # Default env is dev; HSTS must not be asserted when not serving over TLS.
    with TestClient(create_app()) as client:
        r = client.get("/health")
    assert "Strict-Transport-Security" not in r.headers


def test_docs_paths_exempt_from_csp_in_dev():
    # /openapi.json must stay loadable by Swagger UI (no strict CSP applied).
    with TestClient(create_app()) as client:
        r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "Content-Security-Policy" not in r.headers
    # Base hardening headers still apply everywhere.
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


def test_formula_injection_neutralised_for_all_prefixes():
    for payload in ("=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(A1)", "\t=1+1", "\r=1+1"):
        out = spreadsheet_text(payload)
        assert out.startswith("'"), f"{payload!r} was not neutralised"


def test_benign_spreadsheet_text_unchanged():
    for value in ("hello", "123 Main St", "1.5", "(parenthetical)"):
        assert spreadsheet_text(value) == value
