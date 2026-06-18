"""Ingestion gateway safety: content-validated MIME, zip-bomb limits, scanner wiring."""

from __future__ import annotations

import io
import zipfile

import pytest

from docos.services.ingestion.allowlist import inspect_zip_safety, sniff_mime, sniff_ooxml
from docos.services.ingestion.gateway import IngestionGatewayImpl
from docos.services.ingestion.interface import ScanResult
from docos.services.ingestion.scanner import MalwareScanner, NoopScanner
from docos.storage.local import LocalBlobStore

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _gateway(tmp_path, **kwargs) -> IngestionGatewayImpl:
    return IngestionGatewayImpl(
        blob_store=LocalBlobStore(str(tmp_path / "blobs")),
        allowed_mimes={"text/plain", "application/pdf", _DOCX},
        max_bytes=50 * 1024 * 1024,
        **kwargs,
    )


def test_ooxml_classified_by_contents_not_extension(sample_docx_bytes):
    # A real docx renamed with a misleading extension is still detected as docx.
    assert sniff_ooxml(sample_docx_bytes) == _DOCX
    assert sniff_mime("totally-a-spreadsheet.xlsx", sample_docx_bytes) == _DOCX


def test_plain_zip_without_ooxml_markers_is_not_trusted():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("evil.txt", "not office")
    data = buf.getvalue()
    # Even named .docx, a non-OOXML zip stays application/zip (and is rejected by allow-list).
    assert sniff_mime("payload.docx", data) == "application/zip"


def test_ooxml_sniffer_does_not_bless_over_entry_cap_archive():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        for i in range(2100):
            zf.writestr(f"word/junk{i}.xml", "x")
    assert sniff_ooxml(buf.getvalue()) is None
    assert sniff_mime("payload.docx", buf.getvalue()) == "application/zip"


def test_zip_bomb_rejected_by_entry_count():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(50):
            zf.writestr(f"f{i}.txt", "x")
    reason = inspect_zip_safety(
        buf.getvalue(), max_entries=10, max_uncompressed=10_000_000, max_ratio=1000
    )
    assert reason is not None and "too many entries" in reason


def test_zip_bomb_rejected_by_compression_ratio():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", b"0" * 5_000_000)  # compresses tiny, expands huge
    reason = inspect_zip_safety(
        buf.getvalue(), max_entries=2000, max_uncompressed=10_000_000, max_ratio=50
    )
    assert reason is not None and "ratio" in reason


async def test_gateway_rejects_zip_bomb(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        for i in range(5000):
            zf.writestr(f"word/junk{i}.xml", "x")
    result = await _gateway(tmp_path, zip_max_entries=100).validate("a.docx", buf.getvalue())
    assert result.ok is False


async def test_noop_scanner_passes_offline(tmp_path):
    gw = _gateway(tmp_path, scanner=NoopScanner(), fail_closed=False)
    scan = await gw.scan(b"clean bytes")
    assert scan.clean is True


async def test_real_scanner_fails_closed_when_unavailable(tmp_path):
    class Broken(MalwareScanner):
        async def scan(self, data: bytes) -> ScanResult:
            raise ConnectionError("clamd down")

    gw = _gateway(tmp_path, scanner=Broken(), fail_closed=True)
    scan = await gw.scan(b"anything")
    assert scan.clean is False
    assert scan.signature == "scanner-unavailable"


async def test_real_scanner_not_failclosed_propagates(tmp_path):
    class Broken(MalwareScanner):
        async def scan(self, data: bytes) -> ScanResult:
            raise ConnectionError("boom")

    gw = _gateway(tmp_path, scanner=Broken(), fail_closed=False)
    with pytest.raises(ConnectionError):
        await gw.scan(b"x")
