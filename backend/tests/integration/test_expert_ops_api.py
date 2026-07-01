"""Integration tests for DocumentOps autopilot, proof report, review, and batch jobs."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_autopilot_run_clean_before_send(client):
    doc_id = _upload(client, "Clean memo with no sensitive data.")
    res = client.post(
        f"/documents/{doc_id}/autopilot/run",
        json={"goal": "clean_before_send"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["goal"] == "clean_before_send"
    assert body["result"]["job_type"] == "clean_before_send"
    assert body["result"]["verdict"] in ("ready", "needs_review", "blocked")
    assert "blocking_count" in body["result"]
    assert "warning_count" in body["result"]


def test_proof_report_html(client):
    doc_id = _upload(client, "Proposal for Acme. Payment net-30.")
    res = client.get(f"/documents/{doc_id}/proof-report?format=html")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Clean Before Send Report" in res.text


def test_finding_review_stores_correction(client):
    doc_id = _upload(client, "Email jane@example.com here.")
    readiness = client.get(f"/documents/{doc_id}/readiness").json()
    findings = readiness.get("expert_findings") or readiness["result"]["findings"]
    assert findings
    fid = findings[0]["id"]
    res = client.patch(
        f"/documents/{doc_id}/findings/{fid}/review",
        json={"accepted": True, "note": "confirmed in eval"},
    )
    assert res.status_code == 200
    assert res.json()["entry"]["finding_id"] == fid


def test_batch_clean(client):
    a = _upload(client, "Memo A — no issues.")
    b = _upload(client, "Email leak@example.com in body.")
    res = client.post("/jobs/batch-clean", json={"doc_ids": [a, b]})
    assert res.status_code == 200
    results = {r["doc_id"]: r for r in res.json()["results"]}
    assert a in results and b in results


def test_batch_audit(client):
    doc_id = _upload(client, "Invoice #100 for $500 due net-30.")
    res = client.post("/jobs/batch-audit", json={"doc_ids": [doc_id]})
    assert res.status_code == 200
    assert res.json()["results"][0]["result"]["job_type"] in (
        "clean_before_send",
        "patch_apply",
    )
