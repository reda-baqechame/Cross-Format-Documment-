"""MIME allow-listing and magic-byte sniffing.

We never trust the client-supplied content type alone: we sniff magic bytes and
require the result to be on the configured allow-list.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

# Minimal magic-byte signatures -> canonical mime. Office files are ZIP containers,
# so the detected mime is refined by inspecting the package contents downstream.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"PK\x03\x04", "application/zip"),  # docx/xlsx/pptx container
    (b"{\\rtf", "application/rtf"),
]

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_SNIFF_MAX_ZIP_ENTRIES = 2000

# OOXML package markers, checked against the *contents* of the zip — never the filename, so a
# renamed or extension-spoofed file can't masquerade as a different (or trusted) type.
_OOXML_MARKERS: list[tuple[str, str]] = [
    ("word/", _DOCX),
    ("xl/", _XLSX),
    ("ppt/", _PPTX),
]


def sniff_ooxml(data: bytes) -> str | None:
    """Classify a zip as docx/xlsx/pptx by package contents, or ``None`` if it isn't OOXML."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            has_content_types = False
            seen_prefixes: set[str] = set()
            for index, info in enumerate(zf.infolist(), start=1):
                if index > _SNIFF_MAX_ZIP_ENTRIES:
                    return None
                name = info.filename
                if name == "[Content_Types].xml":
                    has_content_types = True
                for prefix, mime in _OOXML_MARKERS:
                    if name.startswith(prefix):
                        seen_prefixes.add(mime)
    except zipfile.BadZipFile:
        return None
    if not has_content_types:
        return None
    for _prefix, mime in _OOXML_MARKERS:
        if mime in seen_prefixes:
            return mime
    return None


def inspect_zip_safety(
    data: bytes, *, max_entries: int, max_uncompressed: int, max_ratio: int
) -> str | None:
    """Return a rejection reason if the archive looks like a zip bomb, else ``None``.

    Reads only the central directory (declared sizes) — no decompression — so it is safe to
    run against a hostile archive.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile:
        return "the archive is corrupt or not a valid zip"
    if len(infos) > max_entries:
        return f"the archive has too many entries ({len(infos)} > {max_entries})"
    total_uncompressed = sum(i.file_size for i in infos)
    total_compressed = sum(i.compress_size for i in infos)
    if total_uncompressed > max_uncompressed:
        return "the archive expands too large (possible zip bomb)"
    if total_compressed > 0 and total_uncompressed / total_compressed > max_ratio:
        return "the archive's compression ratio is too high (possible zip bomb)"
    return None


def sniff_mime(filename: str, data: bytes) -> str:
    """Best-effort content type from magic bytes; OOXML is verified by package contents."""
    head = data[:16]
    for sig, mime in _SIGNATURES:
        if head.startswith(sig):
            if mime == "application/zip":
                # Trust contents, not the extension: a non-OOXML zip stays "application/zip"
                # (and is rejected by the allow-list) regardless of what it's named.
                return sniff_ooxml(data) or "application/zip"
            return mime
    # Fall back to plain text when bytes decode as UTF-8.
    try:
        data[:4096].decode("utf-8")
        ext = Path(filename).suffix.lower()
        if ext in {".md", ".markdown"}:
            return "text/markdown"
        if ext == ".csv":
            return "text/csv"
        if ext in {".html", ".htm"}:
            return "text/html"
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def is_allowed(mime: str, allowed: set[str]) -> bool:
    return mime in allowed
