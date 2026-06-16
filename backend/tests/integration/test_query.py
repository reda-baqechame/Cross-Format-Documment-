"""End-to-end document Q&A + summary over the offline (deterministic) path."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_ask_returns_cited_answer(client):
    doc_id = _upload(
        client,
        "Our headquarters are in Berlin.\n\n"
        "Refunds are available within 30 days of purchase.\n\n"
        "Support is reachable by email.",
    )
    res = client.post(
        f"/documents/{doc_id}/ask", json={"question": "How long do I have for a refund?"}
    )
    assert res.status_code == 200
    body = res.json()
    assert "30 days" in body["answer"]
    assert body["used_llm"] is False  # offline noop → deterministic
    assert any("Refunds" in c["excerpt"] for c in body["citations"])


def test_ask_with_no_match_is_graceful(client):
    doc_id = _upload(client, "This document is about gardening tools.")
    body = client.post(
        f"/documents/{doc_id}/ask", json={"question": "quantum chromodynamics"}
    ).json()
    assert body["citations"] == []
    assert "couldn't find" in body["answer"].lower()


def test_summary_endpoint(client):
    doc_id = _upload(
        client, "Project Apollo overview. It landed humans on the Moon.\n\nBudget details follow."
    )
    body = client.get(f"/documents/{doc_id}/summary").json()
    assert "Project Apollo overview." in body["summary"]
    assert len(body["citations"]) >= 1
