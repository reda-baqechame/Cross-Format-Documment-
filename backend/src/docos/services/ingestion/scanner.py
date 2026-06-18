"""Malware scanning.

``NoopScanner`` is the default so the system runs with zero external dependencies.
``ClamAVScanner`` is the extension point for real scanning in enterprise/cloud modes.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from abc import ABC, abstractmethod

from docos.services.ingestion.interface import ScanResult

_CHUNK = 64 * 1024
_TIMEOUT_S = 30


class MalwareScanner(ABC):
    @abstractmethod
    async def scan(self, data: bytes) -> ScanResult: ...


class NoopScanner(MalwareScanner):
    """Passes everything. Safe for local/offline dev only."""

    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=True)


class ClamAVScanner(MalwareScanner):
    """Stream bytes to a clamd daemon over the INSTREAM protocol.

    Raises on connection/protocol errors so the gateway can fail closed (reject the upload)
    rather than waving an unscanned file through.
    """

    def __init__(self, host: str = "localhost", port: int = 3310) -> None:
        self.host = host
        self.port = port

    async def scan(self, data: bytes) -> ScanResult:
        return await asyncio.to_thread(self._scan_sync, data)

    def _scan_sync(self, data: bytes) -> ScanResult:
        with socket.create_connection((self.host, self.port), timeout=_TIMEOUT_S) as sock:
            sock.settimeout(_TIMEOUT_S)
            sock.sendall(b"zINSTREAM\x00")
            view = memoryview(data)
            for i in range(0, len(data), _CHUNK):
                chunk = view[i : i + _CHUNK]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))  # zero-length chunk terminates the stream

            reply = b""
            while b"\x00" not in reply:
                buf = sock.recv(4096)
                if not buf:
                    break
                reply += buf

        text = reply.decode("utf-8", "replace").strip().strip("\x00").strip()
        if text.endswith("OK"):
            return ScanResult(clean=True)
        if "FOUND" in text:
            # e.g. "stream: Eicar-Test-Signature FOUND"
            name = text.split(":", 1)[-1].strip()
            if name.endswith("FOUND"):
                name = name[: -len("FOUND")].strip()
            return ScanResult(clean=False, signature=name or "malware")
        raise RuntimeError(f"clamav scan error: {text!r}")
