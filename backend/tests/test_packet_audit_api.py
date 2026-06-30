"""Integration tests for the /packets expert-audit API.

Uses the same TestClient + SQLite fixtures as the rest of the suite. Proves the full
HTTP path: create packet → upload + add docs → run audit → read cited report → isolation
across owners. The audit runs against synthetic TXT docs so it is fully offline.
"""

from __future__ import annotations

import io


def _upload_txt(client, filename: str, text: str) -> str:
    """Upload a TXT doc and return its id."""
    r = client.post(
        "/documents",
        files={"file": (filename, io.BytesIO(text.encode()), "text/plain")},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["doc_id"]


def _two_doc_packet(client) -> str:
    invoice_id = _upload_txt(
        client,
        "invoice.txt",
        "Commercial Invoice\n"
        "Invoice No: INV-9001\n"
        "Country of Origin: Morocco\n"
        "HS Code: 6109100010\n"
        "Total: CAD 14,920.00\n",
    )
    po_id = _upload_txt(
        client,
        "po.txt",
        "Purchase Order\nPO No: PO-9001\nTotal: CAD 13,780.00\n",
    )
    r = client.post("/packets", json={"name": "mismatched", "pack": "import_export"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = client.post(f"/packets/{pid}/documents", json={"document_ids": [invoice_id, po_id]})
    assert r.status_code == 200, r.text
    return pid


def test_create_list_add_and_audit(make_client):
    client = make_client()
    pid = _two_doc_packet(client)

    # list shows it
    assert any(p["id"] == pid for p in client.get("/packets").json())

    # run the audit
    r = client.post(f"/packets/{pid}/audit")
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["verdict"] == "blocked"  # totals mismatch (14920 vs 13780)
    mismatches = [f for f in report["findings"] if f["type"] == "field_mismatch"]
    assert mismatches, "expected a cited total mismatch"
    assert mismatches[0]["severity"] == "blocking"
    # Every cited finding points at real source docs.
    cited_docs = {ev["document_id"] for ev in mismatches[0]["evidence"]}
    assert cited_docs, "mismatch finding must carry evidence"


def test_report_findings_evidence_score_endpoints(make_client):
    client = make_client()
    pid = _two_doc_packet(client)
    assert client.post(f"/packets/{pid}/audit").status_code == 200

    r = client.get(f"/packets/{pid}/report")
    assert r.status_code == 200 and r.json()["verdict"] == "blocked"

    r = client.get(f"/packets/{pid}/findings")
    body = r.json()
    assert body["verdict"] == "blocked"
    assert any(f["severity"] == "blocking" for f in body["findings"])

    r = client.get(f"/packets/{pid}/evidence")
    assert r.status_code == 200
    assert isinstance(r.json()["evidence"], list)

    r = client.get(f"/packets/{pid}/score")
    score = r.json()
    assert score["verdict"] == "blocked"
    assert score["blocking"] >= 1


def test_audit_before_docs_is_conflict(make_client):
    client = make_client()
    r = client.post("/packets", json={"name": "empty", "pack": "import_export"})
    pid = r.json()["id"]
    r = client.post(f"/packets/{pid}/audit")
    assert r.status_code == 409  # no documents


def test_report_before_audit_is_404(make_client):
    client = make_client()
    r = client.post("/packets", json={"name": "x", "pack": "import_export"})
    pid = r.json()["id"]
    assert client.get(f"/packets/{pid}/report").status_code == 404


def test_unknown_pack_rejected(make_client):
    client = make_client()
    r = client.post("/packets", json={"name": "x", "pack": "nope"})
    assert r.status_code == 400


def test_packet_owner_isolation(make_client):
    """A packet created in one session is invisible to another (404, not 403)."""
    owner = make_client()
    pid = _two_doc_packet(owner)

    other = make_client()  # fresh session
    assert other.get(f"/packets/{pid}/report").status_code == 404
    assert other.post(f"/packets/{pid}/audit").status_code == 404
    assert pid not in [p["id"] for p in other.get("/packets").json()]
