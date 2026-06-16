"""PDF page operations — merge, split, reorder, rotate, delete.

The page-manipulation features every PDF tool sells (Smallpdf/iLovePDF/Acrobat), done
faithfully with PyMuPDF. Routes compose these *after* the canonical write-back, so edits
and redactions are already burned in before pages are rearranged — a one-stop pipeline
rather than a separate tool.
"""

from __future__ import annotations

import fitz


def page_count(pdf: bytes) -> int:
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()


def _validate(indices: list[int], count: int) -> None:
    for i in indices:
        if i < 0 or i >= count:
            raise ValueError(f"page index {i} out of range (document has {count} pages)")


def reorder_pages(pdf: bytes, order: list[int]) -> bytes:
    """Return a PDF whose pages are exactly ``order`` (also supports subsetting)."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        _validate(order, doc.page_count)
        if not order:
            raise ValueError("order must list at least one page")
        doc.select(order)
        return doc.tobytes()
    finally:
        doc.close()


def delete_pages(pdf: bytes, pages: list[int]) -> bytes:
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        _validate(pages, doc.page_count)
        keep = [i for i in range(doc.page_count) if i not in set(pages)]
        if not keep:
            raise ValueError("cannot delete every page")
        doc.select(keep)
        return doc.tobytes()
    finally:
        doc.close()


def extract_pages(pdf: bytes, pages: list[int]) -> bytes:
    """Split: return a new PDF containing only ``pages`` (in the given order)."""
    return reorder_pages(pdf, pages)


def rotate_pages(pdf: bytes, pages: list[int], degrees: int) -> bytes:
    """Rotate ``pages`` by ``degrees`` (a multiple of 90), relative to current rotation."""
    if degrees % 90 != 0:
        raise ValueError("degrees must be a multiple of 90")
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        _validate(pages, doc.page_count)
        for i in pages:
            page = doc[i]
            page.set_rotation((page.rotation + degrees) % 360)
        return doc.tobytes()
    finally:
        doc.close()


def merge(pdfs: list[bytes]) -> bytes:
    """Concatenate several PDFs into one, in order."""
    if not pdfs:
        raise ValueError("nothing to merge")
    out = fitz.open()
    try:
        for pdf in pdfs:
            src = fitz.open(stream=pdf, filetype="pdf")
            try:
                out.insert_pdf(src)
            finally:
                src.close()
        return out.tobytes()
    finally:
        out.close()
