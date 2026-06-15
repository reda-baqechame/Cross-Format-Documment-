"""Ingestion gateway interface.

File upload is the product's first security boundary (OWASP). The gateway is the
only path by which external bytes enter the system: it validates type, scans for
malware, and stages bytes into blob storage in a sandboxed manner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class IngestResult(BaseModel):
    ok: bool
    mime: str
    detected_format: str | None = None
    reason: str | None = None


class ScanResult(BaseModel):
    clean: bool
    signature: str | None = None


class IngestionGateway(ABC):
    @abstractmethod
    async def validate(self, filename: str, data: bytes) -> IngestResult:
        """Allow-list + magic-byte sniff. Rejects oversized/unknown/spoofed files."""

    @abstractmethod
    async def scan(self, data: bytes) -> ScanResult:
        """Malware scan."""

    @abstractmethod
    async def stage(self, data: bytes, *, mime: str) -> str:
        """Sandbox + persist bytes to the blob store, returning the blob key."""
