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
