"""Unit tests for the validation engine (services/provenance/validation.py)."""

from __future__ import annotations

import fitz

from docos.services.docengine.registry import default_registry
from docos.services.provenance import validation
from docos.services.provenance.validation import validate_export


def _txt_doc(text: str):
    return default_registry().resolve("text/plain").parse(text.encode())


def _pdf_doc(data: bytes):
    return default_registry().resolve("application/pdf").parse(data)


def test_open_ok_detects_valid_and_garbage(sample_pdf_bytes):
    assert validation._open_ok("pdf", sample_pdf_bytes)[0] is True
    assert validation._open_ok("pdf", b"not a pdf at all")[0] is False
    assert validation._open_ok("md", b"# fine")[0] is True


def test_text_export_passes():
    doc = _txt_doc("Hello world\n\nSecond paragraph.")
    report = validate_export(doc, "md", b"# Hello world\n\nSecond paragraph.\n")
    assert report.ok
    codes = {(f.code, f.level) for f in report.findings}
    assert ("output.opens", "pass") in codes
    assert ("text.retained", "pass") in codes


def test_redaction_leak_is_detected_and_clean_passes():
    doc = _txt_doc("supersecretvalue")
    target = next(n for n in doc.nodes.values() if getattr(n, "text", "") == "supersecretvalue")
    doc.redaction.redacted_node_ids = [target.id]

    leaked = validate_export(doc, "txt", b"oops: supersecretvalue is here")
    assert leaked.ok is False
    assert any(f.code == "redaction.recovery" and f.level == "fail" for f in leaked.findings)

    clean = validate_export(doc, "txt", b"nothing sensitive here")
    assert clean.ok is True
    assert any(f.code == "redaction.recovery" and f.level == "pass" for f in clean.findings)


def test_pdf_page_count_mismatch_fails(sample_pdf_bytes):
    doc = _pdf_doc(sample_pdf_bytes)  # one page
    two = fitz.open()
    two.new_page()
    two.new_page()
    report = validate_export(doc, "pdf", two.tobytes())
    assert report.ok is False
    assert any(f.code == "pages.count" and f.level == "fail" for f in report.findings)


def test_unopenable_output_fails_fast():
    doc = _txt_doc("hello")
    report = validate_export(doc, "pdf", b"definitely not a pdf")
    assert report.ok is False
    assert report.findings[0].code == "output.opens"
    assert report.findings[0].level == "fail"


def test_signature_invalidation_warns():
    doc = _txt_doc("hello world")
    doc.signature.signed = True
    report = validate_export(doc, "txt", b"hello world", signature_valid=False)
    assert any(f.code == "signature.invalidated" and f.level == "warn" for f in report.findings)
    assert report.ok  # a warning is not a failure


def test_status_word():
    doc = _txt_doc("hi there friend")
    report = validate_export(doc, "txt", b"hi there friend")
    assert validation.status(report) in ("pass", "warn")
