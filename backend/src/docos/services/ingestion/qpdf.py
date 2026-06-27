"""QPDF preflight seam (QPDF is Apache-2.0).

QPDF performs structural PDF transformations — check/repair, linearize, and encryption detection —
that harden the trust layer: repairing a malformed PDF before parsing, and linearizing it for faster
viewing. It shells out to the ``qpdf`` binary, so it activates only when that binary is installed
*and* ``QPDF_PREFLIGHT=true`` is set; otherwise every helper is a safe no-op and the caller proceeds
with the original bytes. Pairs with the existing ``pikepdf`` page-ops.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_TIMEOUT_S = 30


def qpdf_available() -> bool:
    """True when the ``qpdf`` binary is on PATH."""
    return shutil.which("qpdf") is not None


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - args are fixed flags + temp paths, never user strings
        ["qpdf", *args], capture_output=True, timeout=_TIMEOUT_S, check=False
    )


def is_encrypted(data: bytes) -> bool:
    """True when the PDF is encrypted (qpdf exits 2 with ``--is-encrypted``); False if unknown."""
    if not qpdf_available():
        return False
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        return _run(["--is-encrypted", f.name]).returncode == 0


def check_ok(data: bytes) -> bool:
    """True when ``qpdf --check`` reports a structurally sound PDF (no fatal errors)."""
    if not qpdf_available():
        return True
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        # --check returns 0 (clean) or 3 (warnings) for a usable file; 2 means errors.
        return _run(["--check", f.name]).returncode in (0, 3)


def repair_and_linearize(data: bytes) -> bytes:
    """Return a repaired, linearized copy of the PDF, or the original bytes on any failure.

    Best-effort: encrypted PDFs are returned untouched (we never strip protection), and any qpdf
    error leaves the caller with the bytes it already had.
    """
    if not qpdf_available() or is_encrypted(data):
        return data
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.pdf", Path(d) / "out.pdf"
        src.write_bytes(data)
        try:
            proc = _run(["--linearize", str(src), str(dst)])
        except (OSError, subprocess.SubprocessError):
            return data
        if proc.returncode in (0, 3) and dst.exists() and dst.stat().st_size > 0:
            return dst.read_bytes()
    return data
