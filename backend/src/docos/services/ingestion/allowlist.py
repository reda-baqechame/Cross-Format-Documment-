"""MIME allow-listing and magic-byte sniffing.

We never trust the client-supplied content type alone: we sniff magic bytes and
require the result to be on the configured allow-list.
"""

from __future__ import annotations

# Minimal magic-byte signatures -> canonical mime. Office files are ZIP containers,
# so the detected mime is refined by extension/inspection downstream.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"PK\x03\x04", "application/zip"),  # docx/xlsx/pptx container
    (b"{\\rtf", "application/rtf"),
]

_OOXML_BY_EXT = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def sniff_mime(filename: str, data: bytes) -> str:
    """Best-effort content type from magic bytes, refined by extension."""
    head = data[:16]
    for sig, mime in _SIGNATURES:
        if head.startswith(sig):
            if mime == "application/zip":
                ext = filename.rsplit(".", 1)[-1].lower()
                return _OOXML_BY_EXT.get(ext, "application/zip")
            return mime
    # Fall back to plain text when bytes decode as UTF-8.
    try:
        data[:4096].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def is_allowed(mime: str, allowed: set[str]) -> bool:
    return mime in allowed
