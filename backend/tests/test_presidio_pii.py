"""Unit tests for the Presidio PII seam (mapper + merge) — no Presidio install required."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import ParagraphNode, RootNode, RunNode
from docos.services.provenance import pii
from docos.services.provenance.presidio import map_results, presidio_available
from docos.services.provenance.sensitive import SensitiveFinding


@dataclass
class _Result:
    entity_type: str
    start: int
    end: int
    score: float = 0.9


def _doc(text: str) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root", children=["p"])
    para = ParagraphNode(id="p", parent_id="root", children=["r"])
    run = RunNode(id="r", parent_id="p", text=text)
    return CanonicalDocument(
        doc_id="d",
        root_id="root",
        nodes={"root": root, "p": para, "r": run},
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )


def test_presidio_absent_in_ci():
    assert presidio_available() is False


def test_map_results_normalizes_and_masks():
    text = "Jane Doe lives in Paris; email jane@example.com"
    results = [
        _Result("PERSON", 0, 8),
        _Result("LOCATION", 18, 23),
        _Result("EMAIL_ADDRESS", 31, 47),
        _Result("PERSON", 0, 8, score=0.1),  # below threshold → dropped
    ]
    findings = map_results("r", text, results)
    cats = [f.category for f in findings]
    assert "person" in cats and "location" in cats
    assert "email" in cats  # overlapping entity normalized to the regex category
    assert len(findings) == 3  # the low-score duplicate is filtered
    person = next(f for f in findings if f.category == "person")
    assert person.label == "Person name"
    assert person.excerpt != "Jane Doe"  # masked, never the raw value


def test_merge_dedupes_overlapping_category_on_same_node():
    regex = [SensitiveFinding(node_id="r", category="email", label="Email address", excerpt="…m")]
    extra = [
        SensitiveFinding(node_id="r", category="email", label="Email address", excerpt="…m"),
        SensitiveFinding(node_id="r", category="person", label="Person name", excerpt="…e"),
    ]
    merged = pii._merge(regex, extra)
    assert len(merged) == 2  # the duplicate email is dropped, the person is added
    assert {f.category for f in merged} == {"email", "person"}


def test_scan_defaults_to_regex_only(monkeypatch):
    monkeypatch.setenv("PII_ENGINE", "regex")
    from docos.settings import get_settings

    get_settings.cache_clear()
    findings = pii.scan(_doc("Contact finance@example.com today"))
    assert any(f.category == "email" for f in findings)
    get_settings.cache_clear()


def test_scan_presidio_falls_back_when_unavailable(monkeypatch):
    """PII_ENGINE=presidio still returns regex findings when Presidio isn't installed (CI case)."""
    monkeypatch.setenv("PII_ENGINE", "presidio")
    from docos.settings import get_settings

    get_settings.cache_clear()
    findings = pii.scan(_doc("Email me at finance@example.com"))
    assert any(f.category == "email" for f in findings)  # regex still works; no crash
    get_settings.cache_clear()
