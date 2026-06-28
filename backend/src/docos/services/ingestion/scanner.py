"""Malware / content-defense scanning.

``ContentDefenseScanner`` is the default: a deterministic, fully-offline control that blocks
unambiguous threats in uploaded bytes (EICAR test signature, embedded native executables, PDF
launch actions, and Office VBA macros) with no external dependencies. It is NOT a substitute for
signature-based antivirus on novel malware — ``ClamAVScanner`` adds that when a clamd daemon is
available, and ``CompositeScanner`` chains both so the heuristic layer always runs first.

``NoopScanner`` remains available for explicit offline-dev opt-out (``SCANNER=noop``), but it is
no longer the default, so public uploads are never waved through unscanned.
"""

from __future__ import annotations

import asyncio
import re
import socket
import struct
import zipfile
from abc import ABC, abstractmethod
from io import BytesIO

from docos.services.ingestion.interface import ScanResult

_CHUNK = 64 * 1024
_TIMEOUT_S = 30

# The EICAR anti-malware test string (not real malware) — the industry-standard way to prove a
# scanner is actually inspecting content. https://www.eicar.org/download-anti-malware-testfile/
_EICAR = (
    rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)

# Native-executable magics that should never appear at the start of a document upload.
_EXEC_MAGICS: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Executable.PE"),  # Windows PE/DOS
    (b"\x7fELF", "Executable.ELF"),  # Linux/Unix ELF
    (b"\xca\xfe\xba\xbe", "Executable.MachO-or-Java"),  # Mach-O fat / Java class
    (b"\xfe\xed\xfa\xce", "Executable.MachO"),  # Mach-O 32-bit
    (b"\xfe\xed\xfa\xcf", "Executable.MachO"),  # Mach-O 64-bit
    (b"\xcf\xfa\xed\xfe", "Executable.MachO"),  # Mach-O 64-bit LE
    (b"#!/", "Executable.Script"),  # shebang script
)

# The DOS stub string is present in essentially every Windows PE; finding it embedded inside an
# allowed container (e.g. a polyglot PDF) is a strong signal of a smuggled executable.
_PE_STUB = b"This program cannot be run in DOS mode"

# PDF tokens that launch external programs / auto-run code. ``/Launch`` is almost never legitimate
# in a document; we block it outright. (Plain ``/JavaScript`` is intentionally NOT blocked here —
# it is common in legitimate AcroForms — but a launch action is a different class of threat.)
_PDF_LAUNCH = re.compile(rb"/Launch\b")

# OLE2 / Compound File Binary header (legacy .doc/.xls/.ppt and embedded OLE objects).
_CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class MalwareScanner(ABC):
    @abstractmethod
    async def scan(self, data: bytes) -> ScanResult: ...


class NoopScanner(MalwareScanner):
    """Passes everything. Safe for explicit local/offline dev opt-out only."""

    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=True)


class ContentDefenseScanner(MalwareScanner):
    """Deterministic, offline content-defense. Blocks unambiguous threats with no external infra.

    Detection layers (all high-confidence / low false-positive on legitimate documents):

    * **EICAR** test signature anywhere in the bytes.
    * **Native executables** — a recognised executable magic at offset 0, or the embedded Windows
      PE DOS-stub string (catches polyglot/smuggled binaries).
    * **PDF launch actions** — ``/Launch`` tokens that run external programs.
    * **Office macros** — a ``vbaProject.bin`` member inside an OOXML (zip) upload, or a VBA
      ``_VBA_PROJECT`` stream inside a legacy OLE/CFB document.

    Honesty note: this is content-defense, not signature AV. It will not catch novel/obfuscated
    malware the way ClamAV's signature DB does — chain ``ClamAVScanner`` (``SCANNER=clamav``) for
    that. But it guarantees public uploads are inspected, not waved through.
    """

    async def scan(self, data: bytes) -> ScanResult:
        return await asyncio.to_thread(self._scan_sync, data)

    def _scan_sync(self, data: bytes) -> ScanResult:
        if not data:
            return ScanResult(clean=True)

        if _EICAR in data:
            return ScanResult(clean=False, signature="Eicar-Test-Signature")

        for magic, name in _EXEC_MAGICS:
            if data.startswith(magic):
                return ScanResult(clean=False, signature=name)
        if _PE_STUB in data:
            return ScanResult(clean=False, signature="Executable.PE.Embedded")

        head = data[:5]
        if head == b"%PDF-" and _PDF_LAUNCH.search(data):
            return ScanResult(clean=False, signature="Pdf.Exploit.LaunchAction")

        macro = self._detect_macros(data)
        if macro is not None:
            return ScanResult(clean=False, signature=macro)

        return ScanResult(clean=True)

    @staticmethod
    def _detect_macros(data: bytes) -> str | None:
        # OOXML (.docx/.xlsx/.pptx are zips); a macro project means a macro-enabled payload.
        if data[:2] == b"PK":
            try:
                with zipfile.ZipFile(BytesIO(data)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith("vbaproject.bin"):
                            return "Office.Macro.VBA"
            except zipfile.BadZipFile:
                return None
        # Legacy OLE/CFB documents embed VBA as a named stream.
        elif data[:8] == _CFB_MAGIC and b"_VBA_PROJECT" in data:
            return "Office.Macro.VBA.Legacy"
        return None


class CompositeScanner(MalwareScanner):
    """Run several scanners in order; the first non-clean verdict wins.

    Used to layer the always-on heuristic content-defense in front of signature AV so both run.
    """

    def __init__(self, scanners: list[MalwareScanner]) -> None:
        self._scanners = scanners

    async def scan(self, data: bytes) -> ScanResult:
        for scanner in self._scanners:
            result = await scanner.scan(data)
            if not result.clean:
                return result
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
