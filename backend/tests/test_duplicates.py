"""Near-duplicate detection (rapidfuzz) — unit + API."""

from __future__ import annotations

from docos.services.provenance.duplicates import group_duplicates, similarity


def test_similarity_bounds():
    assert similarity("the quick brown fox", "the quick brown fox") == 1.0
    assert similarity("alpha beta gamma", "totally unrelated words here") < 0.5
    assert similarity("", "anything") == 0.0


def test_group_duplicates_clusters_near_identical():
    items = [
        ("a", "Invoice 42 total due 1,200 USD net 30"),
        ("b", "Invoice 42 total due 1,200 USD net 30 "),  # trivially different
        ("c", "Completely different memo about office plants"),
    ]
    groups = group_duplicates(items, threshold=0.9)
    assert len(groups) == 1
    g = groups[0]
    assert set(g.doc_ids) == {"a", "b"}
    assert g.similarity >= 0.9
    assert "c" not in g.doc_ids


def test_group_duplicates_threshold_excludes_loose_matches():
    items = [("a", "red green blue"), ("b", "red green orange")]
    assert group_duplicates(items, threshold=0.99) == []


def test_duplicates_endpoint(client):
    body = b"Invoice 7 amount 500 dollars due on receipt"
    client.post("/documents", files={"file": ("a.txt", body, "text/plain")})
    client.post("/documents", files={"file": ("b.txt", body + b" ", "text/plain")})
    other = b"Unrelated grocery list eggs milk"
    client.post("/documents", files={"file": ("c.txt", other, "text/plain")})

    resp = client.get("/documents/duplicates")
    assert resp.status_code == 200, resp.text
    groups = resp.json()["groups"]
    assert len(groups) == 1
    assert len(groups[0]["doc_ids"]) == 2
    assert groups[0]["similarity"] >= 0.9
