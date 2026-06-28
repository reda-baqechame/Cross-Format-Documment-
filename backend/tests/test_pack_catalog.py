"""Pack catalog — discoverable registry of installed business packs."""

from __future__ import annotations

from docos.services.packs import list_packs


def test_catalog_lists_all_installed_packs():
    packs = list_packs()
    ids = {p.pack_id for p in packs}
    assert {"import_export", "finance", "contracts", "hr"} <= ids


def test_catalog_entries_are_well_formed():
    for p in list_packs():
        assert p.endpoint.startswith("/packs/")
        assert p.capability.startswith("pack_")
        assert p.doc_types


def test_packs_endpoint_returns_catalog(client):
    res = client.get("/packs")
    assert res.status_code == 200
    body = res.json()
    ids = {p["pack_id"] for p in body}
    assert {"import_export", "finance", "contracts", "hr"} <= ids
