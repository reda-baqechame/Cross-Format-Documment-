"""DocumentOps run — end-to-end orchestration (classify → pack → synthesize) + queryable audit."""

from __future__ import annotations


def _upload(client, name, text):
    return client.post(
        "/documents", files={"file": (name, text.encode(), "text/plain")}
    ).json()["doc_id"]


def test_run_executes_pipeline_and_is_replayable(client):
    inv = _upload(
        client, "inv.txt", "Commercial Invoice\nInvoice number: INV-7\nPO Number: PO-2\n"
                           "Total due: 200.00 USD"
    )
    po = _upload(client, "po.txt", "Purchase Order\nPO Number: PO-2\nTotal due: 150.00 USD")

    res = client.post("/documentops/run", json={"doc_ids": [inv, po], "pack": "finance"})
    assert res.status_code == 200
    body = res.json()
    assert body["pack"] == "finance"
    assert body["document_count"] == 2
    assert body["used_llm"] is False
    # The total mismatch (200 vs 150) is surfaced as a blocking finding…
    assert any(f["code"] == "po_total_mismatch" for f in body["findings"])
    # …a deliverable is offered, and next actions are proposed (gated), not executed.
    assert "pdf" in body["report_formats"] and body["report_endpoint"] == "/packs/finance/report"
    assert any(a["kind"] == "route_approval" for a in body["gated_actions"])

    run_id = body["run_id"]
    replay = client.get(f"/documentops/runs/{run_id}")
    assert replay.status_code == 200
    assert replay.json()["run_id"] == run_id
    assert replay.json()["summary"] == body["summary"]


def test_run_infers_pack_when_unspecified(client):
    inv = _upload(client, "inv.txt", "Commercial Invoice\nInvoice number: INV-1\nTotal due: 9 USD")
    res = client.post("/documentops/run", json={"doc_ids": [inv]})
    assert res.status_code == 200
    assert res.json()["pack"] in {"finance", "import-export"}


def test_run_requires_documents(client):
    assert client.post("/documentops/run", json={"doc_ids": ["nope"]}).status_code == 404


def test_run_is_owner_scoped(make_client):
    a, b = make_client(), make_client()
    inv = _upload(a, "inv.txt", "Commercial Invoice\nInvoice number: X\nTotal due: 1 USD")
    run_id = a.post("/documentops/run", json={"doc_ids": [inv], "pack": "finance"}).json()["run_id"]
    # A different session must not be able to replay another owner's run.
    assert b.get(f"/documentops/runs/{run_id}").status_code == 404
