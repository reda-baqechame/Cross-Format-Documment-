"""Redaction proof: zero recoverable secret bytes across export formats (+ a leak self-test)."""

from __future__ import annotations

import sys
from pathlib import Path

_EVALS = Path(__file__).resolve().parents[2] / "evals"
sys.path.insert(0, str(_EVALS))

from redaction_proof.harness import (  # noqa: E402
    CONTROL,
    SECRET,
    _find,
    build_redacted_document,
    run,
)

from docos.services.docengine.writers.docx_writer import model_to_docx  # noqa: E402


def test_redacted_secret_is_unrecoverable_in_all_formats():
    for r in run():
        assert not r.secret_locations, f"{r.fmt}: secret recoverable at {r.secret_locations}"
        assert r.control_present, f"{r.fmt}: non-redacted control was lost"


def test_scanner_detects_a_real_leak_self_test():
    # Negative control: the scanner must find the secret when it IS present, otherwise a "clean"
    # verdict above would be meaningless.
    assert _find(b"prefix " + SECRET.encode() + b" suffix", SECRET) == ["raw-bytes"]
    # And inside a zip part.
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", f"<t>{SECRET}</t>")
    assert any("zip:" in loc for loc in _find(buf.getvalue(), SECRET))


def test_without_redaction_the_secret_would_leak():
    # Prove the export path *does* emit the secret when it is NOT redacted — so the redaction set is
    # what removes it, not some unrelated dropping of content.
    doc = build_redacted_document()
    doc.redaction.redacted_node_ids = []  # un-redact everything
    leaked = _find(model_to_docx(doc), SECRET)
    assert leaked, "expected the un-redacted secret to appear in the docx export"
    assert CONTROL  # control constant exists/used


def test_pdf_write_back_redaction_is_unrecoverable():
    # The PDF export path (parse -> redact -> write_back_pdf) must leave zero recoverable secret
    # bytes in raw bytes, the text layer, or decompressed content streams; the control survives.
    from redaction_proof.harness import _find_pdf, build_pdf_and_redact

    out = build_pdf_and_redact()
    assert out[:5] == b"%PDF-"
    assert _find_pdf(out, SECRET) == [], "secret recoverable in the redacted PDF"
    assert _find_pdf(out, CONTROL), "non-redacted control was lost from the PDF"


def test_pdf_scanner_detects_a_real_leak_self_test():
    # The PDF scanner must find a secret when it IS present (raw + text layer), so a "clean"
    # verdict on the redacted PDF is meaningful.
    import io

    from redaction_proof.harness import _find_pdf
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, 842))
    c.drawString(72, 700, f"{SECRET} present and recoverable")
    c.save()
    hits = _find_pdf(buf.getvalue(), SECRET)
    assert "raw-bytes" in hits or "text-layer" in hits
