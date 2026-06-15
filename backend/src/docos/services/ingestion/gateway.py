"""Concrete ingestion gateway wiring allow-list + scanner + blob staging."""

from __future__ import annotations

import uuid

from docos.services.ingestion.allowlist import is_allowed, sniff_mime
from docos.services.ingestion.interface import IngestionGateway, IngestResult, ScanResult
from docos.services.ingestion.scanner import MalwareScanner, NoopScanner
from docos.storage.blob import BlobStore

# Map sniffed mime -> the document-engine format id.
_FORMAT_BY_MIME = {
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/rtf": "rtf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/tiff": "image",
}


class IngestionGatewayImpl(IngestionGateway):
    def __init__(
        self,
        *,
        blob_store: BlobStore,
        allowed_mimes: set[str],
        max_bytes: int,
        scanner: MalwareScanner | None = None,
    ) -> None:
        self.blob_store = blob_store
        self.allowed_mimes = allowed_mimes
        self.max_bytes = max_bytes
        self.scanner = scanner or NoopScanner()

    async def validate(self, filename: str, data: bytes) -> IngestResult:
        if len(data) > self.max_bytes:
            return IngestResult(ok=False, mime="", reason="file exceeds size limit")
        mime = sniff_mime(filename, data)
        if not is_allowed(mime, self.allowed_mimes):
            return IngestResult(ok=False, mime=mime, reason=f"mime not allowed: {mime}")
        return IngestResult(ok=True, mime=mime, detected_format=_FORMAT_BY_MIME.get(mime))

    async def scan(self, data: bytes) -> ScanResult:
        return await self.scanner.scan(data)

    async def stage(self, data: bytes, *, mime: str) -> str:
        key = f"uploads/{uuid.uuid4().hex}"
        await self.blob_store.put(key, data)
        return key
