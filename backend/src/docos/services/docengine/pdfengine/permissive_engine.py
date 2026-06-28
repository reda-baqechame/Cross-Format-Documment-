"""Permissive PdfEngine — pypdf + pikepdf (no AGPL dependencies).

Implements the subset of PDF operations that have clean permissive parity. Selected when
``settings.pdf_engine == "permissive"`` AND pypdf+pikepdf are importable; otherwise the factory
falls back to the PyMuPDF engine.

Parity-covered here (verified by ``tests/test_pdfengine_parity.py``):
    page_count, reorder_pages, delete_pages, extract_pages, rotate_pages, merge
    encrypt_pdf (AES-256 R6 via pikepdf), compress_pdf (pikepdf linearize + stream rewrite)

NOT here (stay on PyMuPDF until fidelity parity is proven — see /api/capabilities warnings):
    watermark_pdf            — needs text stamping; reportlab/pypdf content-stream writing TBD
    text/table extraction    — fitz ``get_text("dict")`` / ``find_tables()`` have no clean drop-in
    redaction write-back     — ``add_redact_annot``/``apply_redactions`` is essentially fitz-unique
    searchable-PDF writing   — invisible-text-layer (render_mode 3) needs pikepdf content streams

Each of those still works (the factory routes them to PyMuPDF), but they carry the AGPL risk and
are honestly flagged until migrated.
"""

from __future__ import annotations

import io

import pikepdf
from pypdf import PdfReader, PdfWriter


def _validate(indices: list[int], count: int) -> None:
    for i in indices:
        if i < 0 or i >= count:
            raise ValueError(f"page index {i} out of range (document has {count} pages)")


def _reader(pdf: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(pdf))


def _writer_bytes(writer: PdfWriter) -> bytes:
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def page_count(pdf: bytes) -> int:
    return len(_reader(pdf).pages)


def reorder_pages(pdf: bytes, order: list[int]) -> bytes:
    """Return a PDF whose pages are exactly ``order`` (also supports subsetting)."""
    reader = _reader(pdf)
    _validate(order, len(reader.pages))
    if not order:
        raise ValueError("order must list at least one page")
    writer = PdfWriter()
    for i in order:
        writer.add_page(reader.pages[i])
    return _writer_bytes(writer)


def delete_pages(pdf: bytes, pages: list[int]) -> bytes:
    reader = _reader(pdf)
    count = len(reader.pages)
    _validate(pages, count)
    drop = set(pages)
    keep = [i for i in range(count) if i not in drop]
    if not keep:
        raise ValueError("cannot delete every page")
    writer = PdfWriter()
    for i in keep:
        writer.add_page(reader.pages[i])
    return _writer_bytes(writer)


def extract_pages(pdf: bytes, pages: list[int]) -> bytes:
    return reorder_pages(pdf, pages)


def rotate_pages(pdf: bytes, pages: list[int], degrees: int) -> bytes:
    """Rotate ``pages`` by ``degrees`` (a multiple of 90), relative to current rotation."""
    if degrees % 90 != 0:
        raise ValueError("degrees must be a multiple of 90")
    reader = _reader(pdf)
    count = len(reader.pages)
    _validate(pages, count)
    writer = PdfWriter()
    for i in range(count):
        page = reader.pages[i]
        if i in set(pages):
            page.rotate(degrees)
        writer.add_page(page)
    return _writer_bytes(writer)


def merge(pdfs: list[bytes]) -> bytes:
    """Concatenate several PDFs into one, in order."""
    if not pdfs:
        raise ValueError("nothing to merge")
    writer = PdfWriter()
    for pdf in pdfs:
        writer.append(io.BytesIO(pdf))
    return _writer_bytes(writer)


def encrypt_pdf(
    pdf: bytes, user_password: str, owner_password: str | None = None, *, allow_print: bool = True
) -> bytes:
    """Password-protect a PDF with AES-256 (R6). Accessibility always allowed; print optional."""
    if not user_password:
        raise ValueError("a password is required")
    allow = pikepdf.Permissions(
        accessibility=True, print_lowres=allow_print, print_highres=allow_print
    )
    with pikepdf.open(io.BytesIO(pdf)) as pdf_obj:
        buf = io.BytesIO()
        pdf_obj.save(
            buf,
            encryption=pikepdf.Encryption(
                owner=owner_password or user_password,
                user=user_password,
                R=6,
                allow=allow,
            ),
        )
    return buf.getvalue()


def compress_pdf(pdf: bytes) -> bytes:
    """Shrink a PDF: drop unreferenced objects, linearize, and rewrite object streams."""
    with pikepdf.open(io.BytesIO(pdf)) as pdf_obj:
        pdf_obj.remove_unreferenced_resources()
        buf = io.BytesIO()
        pdf_obj.save(
            buf,
            linearize=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    return buf.getvalue()


def watermark_pdf(pdf: bytes, text: str) -> bytes:
    """Watermark is not yet implemented permissively (no clean text-stamping without reportlab).

    Raises ``NotImplementedError`` so the factory can fall back to PyMuPDF rather than silently
    producing an unwatermarked file. This keeps the capability honest: until a permissive
    text-stamp path is benchmarked, watermarking stays on the AGPL engine.
    """
    raise NotImplementedError(
        "permissive watermark not implemented yet — reportlab/pypdf content-stream path pending"
    )
