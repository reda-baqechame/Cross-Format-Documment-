"""Concrete ingestion gateway wiring allow-list + scanner + blob staging."""

from __future__ import annotations

import logging
import uuid

from docos.services.ingestion.allowlist import inspect_zip_safety, is_allowed, sniff_mime
from docos.services.ingestion.interface import IngestionGateway, IngestResult, ScanResult
from docos.services.ingestion.scanner import MalwareScanner, NoopScanner
from docos.storage.blob import BlobStore

logger = logging.getLogger("docos.ingestion")

# Map sniffed mime -> the document-engine format id.
_FORMAT_BY_MIME = {
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/rtf": "rtf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/tiff": "image",
}

# Mimes whose bytes are zip containers and therefore need zip-bomb inspection.
_ZIP_MIMES = {
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class IngestionGatewayImpl(IngestionGateway):
    def __init__(
        self,
        *,
        blob_store: BlobStore,
        allowed_mimes: set[str],
        max_bytes: int,
        scanner: MalwareScanner | None = None,
        fail_closed: bool = False,
        zip_max_entries: int = 2000,
        zip_max_uncompressed: int = 200 * 1024 * 1024,
        zip_max_ratio: int = 100,
    ) -> None:
        self.blob_store = blob_store
        self.allowed_mimes = allowed_mimes
        self.max_bytes = max_bytes
        self.scanner = scanner or NoopScanner()
        # When a real scanner is configured, an unreachable/erroring scanner must reject the
        # upload rather than pass it through unscanned.
        self.fail_closed = fail_closed
        self.zip_max_entries = zip_max_entries
        self.zip_max_uncompressed = zip_max_uncompressed
        self.zip_max_ratio = zip_max_ratio

    async def validate(self, filename: str, data: bytes) -> IngestResult:
        if not data:
            return IngestResult(ok=False, mime="", reason="the file is empty")
        if len(data) > self.max_bytes:
            max_mb = self.max_bytes // (1024 * 1024)
            return IngestResult(
                ok=False, mime="", reason=f"the file is too large (max {max_mb} MB)"
            )
        mime = sniff_mime(filename, data)
        if not is_allowed(mime, self.allowed_mimes):
            return IngestResult(
                ok=False,
                mime=mime,
                reason=(
                    "this file type isn't supported yet — try PDF, Word, Excel, "
                    "PowerPoint, Markdown, CSV, HTML, RTF, an image, or plain text"
                ),
            )
        if mime in _ZIP_MIMES:
            reason = inspect_zip_safety(
                data,
                max_entries=self.zip_max_entries,
                max_uncompressed=self.zip_max_uncompressed,
                max_ratio=self.zip_max_ratio,
            )
            if reason is not None:
                return IngestResult(ok=False, mime=mime, reason=reason)
        return IngestResult(ok=True, mime=mime, detected_format=_FORMAT_BY_MIME.get(mime))

    async def scan(self, data: bytes) -> ScanResult:
        try:
            return await self.scanner.scan(data)
        except Exception as exc:  # noqa: BLE001 - any scanner failure must fail closed
            if self.fail_closed:
                logger.warning("malware scanner unavailable, rejecting upload: %s", exc)
                return ScanResult(clean=False, signature="scanner-unavailable")
            raise

    async def stage(self, data: bytes, *, mime: str) -> str:
        key = f"uploads/{uuid.uuid4().hex}"
        await self.blob_store.put(key, data)
        return key
