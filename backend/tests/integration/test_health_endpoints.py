"""Liveness/readiness/health endpoints."""

from __future__ import annotations


def test_live_is_always_alive(client):
    res = client.get("/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"


def test_ready_passes_on_a_healthy_app(client):
    res = client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["checks"]["table:documents"] == "ok"
    assert body["checks"]["table:document_versions"] == "ok"
    assert body["checks"]["blob_storage"] == "ok"


def test_health_summary_reports_provider_and_storage(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    # Provider/storage/db truthing for the System Status panel.
    for key in ("ai_enabled", "office_editor", "pdf_editor", "blob_backend", "database"):
        assert key in body
    # Offline test config: no LLM provider, structural editors only.
    assert body["ai_enabled"] is False
    assert body["office_editor"] is False
    assert body["pdf_editor"] is False
