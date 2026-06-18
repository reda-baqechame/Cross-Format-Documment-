"""Templates & styles library over the API."""

from __future__ import annotations


def _upload(client, body=b"Template body line one.\n\nSecond paragraph."):
    return client.post("/documents", files={"file": ("t.txt", body, "text/plain")}).json()[
        "doc_id"
    ]


def test_save_list_and_instantiate_template(client):
    doc_id = _upload(client)

    saved = client.post(
        f"/documents/{doc_id}/save-as-template",
        json={"name": "NDA", "description": "Standard mutual NDA"},
    )
    assert saved.status_code == 200
    template_id = saved.json()["id"]

    listed = client.get("/templates").json()["templates"]
    assert any(t["id"] == template_id and t["name"] == "NDA" for t in listed)

    made = client.post(f"/templates/{template_id}/instantiate", json={"title": "ACME NDA"})
    assert made.status_code == 200
    new_doc_id = made.json()["doc_id"]
    assert new_doc_id != doc_id  # a fresh, independent document

    # The new document is a real document: retrievable, with the template's structure.
    model = client.get(f"/documents/{new_doc_id}/model")
    assert model.status_code == 200
    doc = model.json()["document"]
    assert doc["meta"]["title"] == "ACME NDA"

    # Node ids are regenerated — no identifier overlap with the source document.
    src_nodes = set(client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"])
    new_nodes = set(doc["nodes"])
    assert src_nodes.isdisjoint(new_nodes)


def test_instantiated_document_is_editable_and_exportable(client):
    doc_id = _upload(client)
    template_id = client.post(
        f"/documents/{doc_id}/save-as-template", json={"name": "Letter"}
    ).json()["id"]
    new_doc_id = client.post(f"/templates/{template_id}/instantiate", json={}).json()["doc_id"]

    # Export through a model-only writer works without original upload bytes.
    md = client.get(f"/documents/{new_doc_id}/export?format=md")
    assert md.status_code == 200
    assert b"Template body" in md.content


def test_delete_and_missing_template(client):
    doc_id = _upload(client)
    template_id = client.post(
        f"/documents/{doc_id}/save-as-template", json={"name": "X"}
    ).json()["id"]

    assert client.delete(f"/templates/{template_id}").status_code == 204
    assert client.post(f"/templates/{template_id}/instantiate", json={}).status_code == 404
    assert client.get("/templates").json()["templates"] == []


def test_templates_are_session_scoped(make_client):
    alice = make_client()
    bob = make_client()
    doc_id = _upload(alice)
    template_id = alice.post(
        f"/documents/{doc_id}/save-as-template", json={"name": "Private packet"}
    ).json()["id"]

    assert bob.get("/templates").json()["templates"] == []
    assert bob.post(f"/templates/{template_id}/instantiate", json={}).status_code == 404
    assert bob.delete(f"/templates/{template_id}").status_code == 404
    assert any(t["id"] == template_id for t in alice.get("/templates").json()["templates"])


def test_validation_errors(client):
    doc_id = _upload(client)
    blank = client.post(f"/documents/{doc_id}/save-as-template", json={"name": "  "})
    assert blank.status_code == 422
    assert (
        client.post("/documents/nope/save-as-template", json={"name": "n"}).status_code == 404
    )
