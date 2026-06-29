"""New input adapters (Pillar A): email/.eml, JSON, XML → canonical model → existing writers."""

from __future__ import annotations

from docos.services.docengine.adapters.eml import EmlAdapter
from docos.services.docengine.adapters.json_adapter import JsonAdapter
from docos.services.docengine.adapters.xml_adapter import XmlAdapter
from docos.services.docengine.writers.markup import model_to_markdown


def test_eml_parses_headers_and_body():
    raw = (
        b"From: alice@example.com\r\n"
        b"To: bob@example.com\r\n"
        b"Subject: Q3 numbers\r\n"
        b"Date: Mon, 1 Jan 2024 10:00:00 +0000\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Revenue was up 12%.\r\n\r\nSee the attached deck.\r\n"
    )
    doc = EmlAdapter().parse(raw)
    md = model_to_markdown(doc).decode()
    assert "Q3 numbers" in md
    assert "alice@example.com" in md
    assert "Revenue was up 12%." in md


def test_eml_html_body_is_flattened():
    raw = (
        b"Subject: HTML mail\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<html><body><p>Hello <b>world</b></p><p>Second line</p></body></html>"
    )
    md = model_to_markdown(EmlAdapter().parse(raw)).decode()
    assert "Hello" in md and "world" in md and "Second line" in md
    assert "<p>" not in md  # tags flattened


def test_json_array_of_objects_becomes_table():
    data = b'[{"name": "INV-1", "total": 100}, {"name": "INV-2", "total": 250}]'
    md = model_to_markdown(JsonAdapter().parse(data)).decode()
    assert "INV-1" in md and "250" in md and "name" in md


def test_json_nested_object_flattens_to_paths():
    data = b'{"customer": {"name": "Acme", "id": 7}, "total": 99}'
    md = model_to_markdown(JsonAdapter().parse(data)).decode()
    assert "customer.name: Acme" in md and "total: 99" in md


def test_xml_walks_elements():
    data = b'<invoice id="9"><party>Acme</party><total>500</total></invoice>'
    md = model_to_markdown(XmlAdapter().parse(data)).decode()
    assert "invoice" in md and "Acme" in md and "500" in md


def test_xml_is_safe_against_entity_expansion():
    # A billion-laughs payload must not blow up memory/CPU — parsing should fail closed or ignore
    # entities, never expand them.
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]><lolz>&lol2;</lolz>'
    )
    doc = XmlAdapter().parse(bomb)  # must return (degraded) without expanding to huge output
    md = model_to_markdown(doc).decode()
    assert "lollollollollol" not in md


def _upload(client, name, data, mime):
    return client.post("/documents", files={"file": (name, data, mime)})


def test_upload_eml_json_xml_end_to_end(client):
    # The sniffer keys text formats off the extension; uploads must parse end-to-end.
    eml = _upload(
        client, "mail.eml", b"Subject: Hi\r\n\r\nbody text here", "message/rfc822"
    )
    assert eml.status_code == 200, eml.text

    js = _upload(client, "data.json", b'{"a": 1, "b": "two"}', "application/json")
    assert js.status_code == 200, js.text

    xml = _upload(client, "doc.xml", b"<root><item>hello</item></root>", "application/xml")
    assert xml.status_code == 200, xml.text


def test_new_adapters_are_redaction_aware():
    doc = JsonAdapter().parse(b'{"secret": "TOPSECRET-1", "public": "ok"}')
    secret = next(
        n.id for n in doc.nodes.values()
        if n.type == "run" and "TOPSECRET-1" in (getattr(n, "text", "") or "")
    )
    doc.redaction.redacted_node_ids.append(secret)
    assert "TOPSECRET-1" not in model_to_markdown(doc).decode()
