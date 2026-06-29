"""Cross-document semantic search and the multi-document notebook."""

from __future__ import annotations


def _upload(client, name, text):
    return client.post("/documents", files={"file": (name, text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_semantic_search_ranks_relevant_doc_first(client):
    invoice = _upload(
        client, "invoice.txt", "Invoice total amount due is 1200 dollars payable on receipt."
    )
    recipe = _upload(
        client, "recipe.txt", "Mix flour sugar butter and bake the cake for forty minutes."
    )

    hits = client.get("/search/semantic", params={"q": "amount due payable invoice"}).json()
    assert hits, "expected at least one ranked hit"
    assert hits[0]["doc_id"] == invoice
    ids = [h["doc_id"] for h in hits]
    if recipe in ids:  # if it scores at all, it must rank below the invoice
        assert ids.index(invoice) < ids.index(recipe)
    assert hits[0]["snippet"]


def test_semantic_search_empty_query_terms(client):
    _upload(client, "a.txt", "some content here")
    # a query of only stopwords yields no ranked hits rather than erroring
    assert client.get("/search/semantic", params={"q": "the and of"}).json() == []


def test_notebook_answers_with_cross_document_citations(client):
    d1 = _upload(client, "policy.txt", "Refund requests must be filed within 30 days of purchase.")
    d2 = _upload(client, "hr.txt", "Employees accrue 15 vacation days per year.")

    resp = client.post("/notebook/ask", json={"question": "How many days for a refund?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] == 2
    assert "30 days" in body["answer"]
    cited_docs = [c["doc_id"] for c in body["citations"]]
    assert d1 in cited_docs
    # the refund doc (matches both "refund" and "days") ranks above the HR doc
    assert cited_docs[0] == d1
    if d2 in cited_docs:
        assert cited_docs.index(d1) < cited_docs.index(d2)


def test_notebook_can_scope_to_doc_ids(client):
    d1 = _upload(client, "one.txt", "Project Apollo launches in March.")
    _upload(client, "two.txt", "Project Apollo budget is 5 million.")
    resp = client.post(
        "/notebook/ask", json={"question": "When does Apollo launch?", "doc_ids": [d1]}
    )
    body = resp.json()
    assert body["document_count"] == 1
    assert all(c["doc_id"] == d1 for c in body["citations"])


def test_notebook_no_match(client):
    _upload(client, "x.txt", "Completely unrelated content about gardening.")
    resp = client.post("/notebook/ask", json={"question": "quantum chromodynamics lagrangian"})
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


def test_notebook_requires_question(client):
    assert client.post("/notebook/ask", json={"question": "  "}).status_code == 422


def test_notebook_agent_offline_cites_across_docs(client):
    d1 = _upload(client, "policy.txt", "Refund requests must be filed within 30 days of purchase.")
    _upload(client, "hr.txt", "Employees accrue 15 vacation days per year.")
    resp = client.post("/notebook/agent", json={"goal": "How many days for a refund?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["used_llm"] is False  # offline noop → deterministic cross-document analysis
    assert any(s["tool"] == "search" for s in body["steps"])
    assert "30 days" in body["answer"]
    assert any(c["doc_id"] == d1 for c in body["citations"])


def test_notebook_agent_requires_goal(client):
    assert client.post("/notebook/agent", json={"goal": "  "}).status_code == 422
