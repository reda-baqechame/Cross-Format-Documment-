"""End-to-end: the Send-Ready Check endpoint over the FastAPI client."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_clean_document_reads_ready(client):
    doc_id = _upload(client, "A clean memo with nothing sensitive in it.")
    report = client.get(f"/documents/{doc_id}/readiness").json()["report"]
    assert report["verdict"] == "ready"
    assert {c["id"] for c in report["checks"]} >= {"pending_redactions", "exposed_pii"}


def test_document_with_pii_needs_fixes_and_offers_redact(client):
    doc_id = _upload(client, "Email jane@example.com, SSN 123-45-6789.")
    report = client.get(f"/documents/{doc_id}/readiness").json()["report"]
    assert report["verdict"] == "needs_fixes"
    pii = next(c for c in report["checks"] if c["id"] == "exposed_pii")
    assert pii["fixable"] is True and pii["fix_action"] == "redact_pii"
    # Detail is safe to show — it must not leak the raw values.
    assert "jane@example.com" not in pii["detail"]
    assert "123-45-6789" not in pii["detail"]


def test_readiness_flips_to_ready_after_redacting(client):
    doc_id = _upload(client, "Email jane@example.com here.")
    assert client.get(f"/documents/{doc_id}/readiness").json()["report"]["verdict"] == "needs_fixes"
    client.post(f"/documents/{doc_id}/redact-sensitive")
    assert client.get(f"/documents/{doc_id}/readiness").json()["report"]["verdict"] == "ready"


def test_client_packet_business_readiness_checks_surface_through_api(client):
    doc_id = _upload(client, "Proposal for client website service. We can start after approval.")
    report = client.get(f"/documents/{doc_id}/readiness").json()["report"]
    checks = {check["id"]: check for check in report["checks"]}

    assert report["verdict"] == "needs_fixes"
    assert checks["scope_clarity"]["status"] == "warn"
    assert checks["payment_terms"]["status"] == "warn"
    assert checks["signature_acceptance"]["status"] == "warn"
    assert checks["client_onboarding"]["status"] == "warn"
    assert checks["scope_change_control"]["status"] == "warn"
    assert checks["payment_terms"]["fixable"] is False


def test_readiness_html_report_download(client):
    doc_id = _upload(client, "Proposal for Acme. Payment net-30 upon signature.")
    res = client.get(f"/documents/{doc_id}/readiness/report?format=html")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    body = res.text
    assert "Client Packet Readiness Report" in body
    assert "Recommended next steps" in body
    assert "jane@example.com" not in body
