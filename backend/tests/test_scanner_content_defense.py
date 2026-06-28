"""ContentDefenseScanner — the offline, deterministic upload control that is now the default.

These tests pin the security contract: known-bad content is blocked with a clear signature, and
legitimate documents pass. This is the proof that public uploads are no longer waved through.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from docos.services.ingestion.interface import ScanResult
from docos.services.ingestion.scanner import (
    CompositeScanner,
    ContentDefenseScanner,
    MalwareScanner,
)

# The real EICAR test string (harmless; the industry-standard scanner self-test).
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


async def test_eicar_is_blocked():
    result = await ContentDefenseScanner().scan(b"prefix " + EICAR + b" suffix")
    assert result.clean is False
    assert result.signature == "Eicar-Test-Signature"


async def test_windows_executable_blocked():
    pe = b"MZ\x90\x00" + b"\x00" * 64 + b"This program cannot be run in DOS mode\r\n"
    result = await ContentDefenseScanner().scan(pe)
    assert result.clean is False
    assert result.signature.startswith("Executable")


async def test_elf_executable_blocked():
    result = await ContentDefenseScanner().scan(b"\x7fELF\x02\x01\x01\x00rest")
    assert result.clean is False
    assert result.signature == "Executable.ELF"


async def test_embedded_pe_stub_blocked_in_polyglot():
    # A file that starts as a PDF but smuggles a PE payload (DOS stub string embedded).
    polyglot = b"%PDF-1.7\n...filler...\nThis program cannot be run in DOS mode\n...trailer"
    result = await ContentDefenseScanner().scan(polyglot)
    assert result.clean is False
    assert result.signature == "Executable.PE.Embedded"


async def test_pdf_launch_action_blocked():
    pdf = b"%PDF-1.7\n1 0 obj<</Type/Action/S/Launch/F(calc.exe)>>endobj\ntrailer"
    result = await ContentDefenseScanner().scan(pdf)
    assert result.clean is False
    assert result.signature == "Pdf.Exploit.LaunchAction"


async def test_ooxml_macro_blocked():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")
        zf.writestr("word/vbaProject.bin", b"\x00\x01macro payload")
    result = await ContentDefenseScanner().scan(buf.getvalue())
    assert result.clean is False
    assert result.signature == "Office.Macro.VBA"


async def test_clean_pdf_passes():
    pdf = b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    result = await ContentDefenseScanner().scan(pdf)
    assert result.clean is True
    assert result.signature is None


async def test_clean_docx_without_macros_passes():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document>Hello</document>")
    result = await ContentDefenseScanner().scan(buf.getvalue())
    assert result.clean is True


async def test_plain_text_with_word_javascript_is_not_a_false_positive():
    # A document that merely mentions "/Launch" or "javascript" in prose must not be blocked
    # unless it is an actual PDF launch action.
    text = b"This article discusses /Launch semantics and javascript: URIs in plain prose."
    result = await ContentDefenseScanner().scan(text)
    assert result.clean is True


async def test_empty_input_is_clean():
    assert (await ContentDefenseScanner().scan(b"")).clean is True


class _AlwaysClean(MalwareScanner):
    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=True)


class _AlwaysInfected(MalwareScanner):
    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=False, signature="Test.Sig")


async def test_composite_first_nonclean_wins():
    composite = CompositeScanner([ContentDefenseScanner(), _AlwaysInfected()])
    # Heuristic passes a clean file, then the second scanner flags it.
    result = await composite.scan(b"%PDF-1.7 clean")
    assert result.clean is False
    assert result.signature == "Test.Sig"


async def test_composite_heuristic_short_circuits():
    # EICAR is caught by the first scanner; the second never needs to run.
    composite = CompositeScanner([ContentDefenseScanner(), _AlwaysClean()])
    result = await composite.scan(EICAR)
    assert result.clean is False
    assert result.signature == "Eicar-Test-Signature"
