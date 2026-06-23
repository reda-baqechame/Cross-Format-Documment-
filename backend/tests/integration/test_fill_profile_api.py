"""Fill Once: save a profile, then autofill a form's matching blank fields."""

from __future__ import annotations


def _upload_form(client) -> str:
    # "Label: ____" blanks become real fields via /fields/detect.
    text = "Name: ______\n\nEmail: ______\n\nNote: keep this"
    doc_id = client.post(
        "/documents", files={"file": ("form.txt", text.encode(), "text/plain")}
    ).json()["doc_id"]
    client.post(f"/documents/{doc_id}/fields/detect")
    return doc_id


def test_save_and_read_profile(client):
    client.put("/fill-profile", json={"data": {"Name": "Ada Lovelace", "Email": "ada@x.com"}})
    data = client.get("/fill-profile").json()["data"]
    assert data["name"] == "Ada Lovelace"  # keys normalised to lowercase
    assert data["email"] == "ada@x.com"


def test_autofill_fills_matching_blank_fields(client):
    client.put("/fill-profile", json={"data": {"Name": "Ada Lovelace", "Email": "ada@x.com"}})
    doc_id = _upload_form(client)

    res = client.post(f"/documents/{doc_id}/autofill").json()
    assert res["filled"] == 2
    assert res["new_version_id"]

    fields = client.get(f"/documents/{doc_id}/fields").json()["fields"]
    by_name = {f["field_name"].lower(): f["value"] for f in fields}
    assert by_name["name"] == "Ada Lovelace"
    assert by_name["email"] == "ada@x.com"


def test_autofill_is_noop_without_profile(client):
    doc_id = _upload_form(client)
    res = client.post(f"/documents/{doc_id}/autofill").json()
    assert res["filled"] == 0
    assert res["new_version_id"] is None
