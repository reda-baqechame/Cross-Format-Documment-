"""TXT adapter parses blocks into paragraphs/runs and exports back."""

from __future__ import annotations

from docos.services.docengine.adapters.txt import TxtAdapter


def test_parses_paragraphs(sample_txt_bytes):
    doc = TxtAdapter().parse(sample_txt_bytes)
    paragraphs = [n for n in doc.nodes.values() if n.type == "paragraph"]
    runs = [n for n in doc.nodes.values() if n.type == "run"]
    assert len(paragraphs) == 3
    assert any("Second paragraph" in r.text for r in runs)


def test_reading_order_is_set(sample_txt_bytes):
    doc = TxtAdapter().parse(sample_txt_bytes)
    paragraphs = [n for n in doc.children_of(doc.root_id) if n.type == "paragraph"]
    assert [p.reading_order for p in paragraphs] == [0, 1, 2]


def test_export_round_trips_text(sample_txt_bytes):
    adapter = TxtAdapter()
    doc = adapter.parse(sample_txt_bytes)
    out = adapter.export(doc, target_mime="text/plain").decode("utf-8")
    assert "Second paragraph" in out
