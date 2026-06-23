"""Cloud IDP + handwriting seam: local fallback by default, provider used when configured."""

from __future__ import annotations

from docos.deps import get_handwriting_provider, get_idp_provider
from docos.services.ocr.handwriting import HandwritingProvider
from docos.services.ocr.idp import IdpField, IdpProvider, _parse_textract


def _upload(client, text: bytes = b"Name: Alice\n\nTotal: $42.00\n") -> str:
    return client.post("/documents", files={"file": ("d.txt", text, "text/plain")}).json()["doc_id"]


def test_idp_falls_back_to_local_extraction(client):
    doc_id = _upload(client)
    res = client.get(f"/documents/{doc_id}/idp-extract")
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "local"
    assert body["used_provider"] is False
    assert "no cloud idp configured" in body["detail"].lower()
    # The deterministic extractor found the labelled fields.
    keys = {f["key"].lower() for f in body["fields"]}
    assert "name" in keys


def test_idp_uses_provider_when_configured(client, monkeypatch):
    class _FakeIdp(IdpProvider):
        name = "external"

        def analyze(self, data: bytes, mime: str) -> list[IdpField]:
            return [IdpField(key="Invoice", value="INV-9", confidence=0.99)]

    client.app.dependency_overrides[get_idp_provider] = lambda: _FakeIdp()
    try:
        doc_id = _upload(client)
        body = client.get(f"/documents/{doc_id}/idp-extract").json()
        assert body["provider"] == "external"
        assert body["used_provider"] is True
        assert body["fields"][0]["key"] == "Invoice"
    finally:
        client.app.dependency_overrides.pop(get_idp_provider, None)


def test_handwriting_augments_image_sources(client, monkeypatch):
    class _FakeHw(HandwritingProvider):
        name = "external"

        def recognize(self, image: bytes, mime: str = "image/png") -> str:
            return "handwritten note"

    # Build a tiny PNG so the upload is an image-source document.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    doc_id = client.post(
        "/documents", files={"file": ("scan.png", buf.getvalue(), "image/png")}
    ).json()["doc_id"]

    client.app.dependency_overrides[get_handwriting_provider] = lambda: _FakeHw()
    try:
        body = client.get(f"/documents/{doc_id}/idp-extract").json()
        hw = [f for f in body["fields"] if f["key"] == "handwriting"]
        assert hw and "handwritten" in hw[0]["value"]
    finally:
        client.app.dependency_overrides.pop(get_handwriting_provider, None)


def test_textract_parser_extracts_key_values():
    # Minimal Textract response: one KEY block linked to a VALUE block, each with a WORD child.
    resp = {
        "Blocks": [
            {
                "Id": "k1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Confidence": 99.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["kw"]},
                    {"Type": "VALUE", "Ids": ["v1"]},
                ],
            },
            {"Id": "kw", "BlockType": "WORD", "Text": "Name"},
            {
                "Id": "v1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["VALUE"],
                "Relationships": [{"Type": "CHILD", "Ids": ["vw"]}],
            },
            {"Id": "vw", "BlockType": "WORD", "Text": "Alice"},
        ]
    }
    fields = _parse_textract(resp)
    assert fields == [IdpField(key="Name", value="Alice", confidence=99.0)]


def test_providers_are_none_by_default():
    assert get_idp_provider() is None
    assert get_handwriting_provider() is None
