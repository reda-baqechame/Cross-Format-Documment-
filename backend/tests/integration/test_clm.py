"""CLM: clause library + renewal tracking (clauses insert as reversible patches; renewals sort)."""

from __future__ import annotations

from docos.services.clm.renewals import normalise_date, suggest_due_dates, urgency


def _txt_doc(client, text: bytes = b"Body line one.\n\nBody line two.") -> str:
    return client.post("/documents", files={"file": ("d.txt", text, "text/plain")}).json()["doc_id"]


def test_clause_crud_and_insert_is_versioned(client):
    doc_id = _txt_doc(client)
    before = len(client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"])

    clause = client.post(
        "/clauses",
        json={"title": "Confidentiality", "body": "Each party keeps the other's data secret.",
              "category": "contract"},
    ).json()
    assert clause["title"] == "Confidentiality"

    listing = client.get("/clauses").json()["clauses"]
    assert any(c["id"] == clause["id"] for c in listing)

    res = client.post(f"/documents/{doc_id}/insert-clause", json={"clause_id": clause["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["inserted"] >= 2  # title heading + a body paragraph
    assert body["new_version_id"]  # committed a new version

    after = len(client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"])
    assert after > before  # nodes actually added

    assert client.delete(f"/clauses/{clause['id']}").status_code == 204
    assert all(c["id"] != clause["id"] for c in client.get("/clauses").json()["clauses"])


def test_clauses_are_session_isolated(make_client):
    a, b = make_client(), make_client()
    a.post("/clauses", json={"title": "Mine", "body": "secret clause"})
    assert a.get("/clauses").json()["clauses"]
    assert b.get("/clauses").json()["clauses"] == []  # other session can't see it


def test_insert_adhoc_clause_without_saving(client):
    doc_id = _txt_doc(client)
    res = client.post(
        f"/documents/{doc_id}/insert-clause",
        json={"title": "Term", "body": "This agreement lasts 12 months."},
    )
    assert res.status_code == 200 and res.json()["inserted"] >= 2


def test_renewal_crud_and_ordering(client):
    client.post("/renewals", json={"title": "Vendor B", "due_date": "2027-03-01"})
    client.post("/renewals", json={"title": "Vendor A", "due_date": "2026-01-15"})
    renewals = client.get("/renewals").json()["renewals"]
    assert [r["due_date"] for r in renewals] == ["2026-01-15", "2027-03-01"]  # sorted asc
    assert all("urgency" in r for r in renewals)

    rid = renewals[0]["id"]
    assert client.delete(f"/renewals/{rid}").status_code == 204
    assert all(r["id"] != rid for r in client.get("/renewals").json()["renewals"])


def test_renewal_rejects_bad_date(client):
    assert client.post("/renewals", json={"title": "x", "due_date": "March 1"}).status_code == 422


def test_renewal_suggestions_from_document(client):
    doc_id = _txt_doc(client, b"Effective 2026-01-01. Renews on 2027-12-31.")
    dates = client.get(f"/documents/{doc_id}/renewal-suggestions").json()["due_dates"]
    assert "2027-12-31" in dates and "2026-01-01" in dates


def test_renewal_helpers_are_pure():
    from datetime import date

    assert normalise_date("01/15/2026") == "2026-01-15"
    assert normalise_date("Jan 15, 2026") == "2026-01-15"
    assert normalise_date("not a date") is None
    today = date(2026, 6, 1)
    assert urgency("2026-01-01", today=today) == "overdue"
    assert urgency("2026-06-20", today=today) == "soon"
    assert urgency("2027-01-01", today=today) == "later"


def test_suggest_due_dates_orders_future_first():
    from datetime import date

    from docos.services.docengine.adapters.txt import TxtAdapter

    doc = TxtAdapter().parse(b"Signed 2025-01-01, expires 2030-05-05, renews 2031-06-06.")
    out = suggest_due_dates(doc, today=date(2026, 1, 1))
    assert out[0] == "2030-05-05"  # earliest future date first
    assert "2025-01-01" in out  # past dates still included, after future ones
