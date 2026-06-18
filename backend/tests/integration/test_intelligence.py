"""End-to-end: typed document intelligence over the canonical model."""

from __future__ import annotations


def _check(insight, check_id):
    return next(c for c in insight["checks"] if c["id"] == check_id)


def test_invoice_intelligence_endpoint(client):
    body = (
        b"INVOICE\n\n"
        b"Invoice Number: INV-2026-091\n\n"
        b"Due Date: 2026-07-01\n\n"
        b"Subtotal: $200.00\n\n"
        b"Tax: $20.00\n\n"
        b"Total Due: $220.00\n"
    )
    doc_id = client.post("/documents", files={"file": ("inv.txt", body, "text/plain")}).json()[
        "doc_id"
    ]

    res = client.get(f"/documents/{doc_id}/intelligence")
    assert res.status_code == 200
    insight = res.json()["insight"]
    assert insight["doc_type"] == "invoice"
    assert _check(insight, "totals_reconcile")["passed"] is True
    assert _check(insight, "has_total")["passed"] is True
    keys = {f["key"] for f in insight["fields"]}
    assert "total" in keys and "invoice_number" in keys


def test_intelligence_is_redaction_aware(client):
    body = b"INVOICE\n\nBill To: Acme\n\nTotal Due: $500.00\n"
    doc_id = client.post("/documents", files={"file": ("inv.txt", body, "text/plain")}).json()[
        "doc_id"
    ]

    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    total_node = next(
        n["id"] for n in model["nodes"].values() if n.get("text") == "Total Due: $500.00"
    )
    client.post(
        f"/documents/{doc_id}/patches", json={"ops": [{"op": "redact", "target_id": total_node}]}
    )

    insight = client.get(f"/documents/{doc_id}/intelligence").json()["insight"]
    # the redacted total must not be read back out
    assert _check(insight, "has_total")["passed"] is False
    assert all("500.00" not in f["value"] for f in insight["fields"])


def test_presentation_intelligence_endpoint(client):
    body = (
        b"Acme Investor Pitch\n\nAgenda\n\nProblem: customers waste time\n\n"
        b"Solution: our product\n\nMarket: TAM is large\n\nTeam: ex-Google\n\n"
        b"The ask: raising a seed round\n\nThank you\n"
    )
    doc_id = client.post("/documents", files={"file": ("deck.txt", body, "text/plain")}).json()[
        "doc_id"
    ]

    insight = client.get(f"/documents/{doc_id}/intelligence").json()["insight"]
    assert insight["doc_type"] in {"presentation", "pitch_deck"}
    assert _check(insight, "has_agenda_or_closing")["passed"] is True
    assert _check(insight, "deck_has_team")["passed"] is True
