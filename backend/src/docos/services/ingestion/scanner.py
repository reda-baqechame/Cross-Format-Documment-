"""Malware scanning.

``NoopScanner`` is the default so the system runs with zero external dependencies.
``ClamAVScanner`` is the extension point for real scanning in enterprise/cloud modes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from docos.services.ingestion.interface import ScanResult


class MalwareScanner(ABC):
    @abstractmethod
    async def scan(self, data: bytes) -> ScanResult: ...


class NoopScanner(MalwareScanner):
    """Passes everything. Safe for local/offline dev only."""

    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=True)


class ClamAVScanner(MalwareScanner):
    """STUB: connect to a clamd socket and stream bytes for scanning."""

    def __init__(self, host: str = "localhost", port: int = 3310) -> None:
        self.host = host
        self.port = port

    async def scan(self, data: bytes) -> ScanResult:
        raise NotImplementedError("ClamAVScanner.scan — wire up clamd for production")
