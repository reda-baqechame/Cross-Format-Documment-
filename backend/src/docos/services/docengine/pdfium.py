"""Permissive PDF page rasterizer (pypdfium2, Apache-2.0 / BSD-3).

PyMuPDF/fitz is AGPL — a commercial-SaaS licensing risk. pypdfium2 wraps Google's PDFium under a
permissive license and ships a self-contained binary wheel, so it is the migration target *off*
AGPL. This module renders pages to PNG exactly like the PyMuPDF rasteriser in ``adapters/pdf.py``,
and is selected via ``PDF_RENDER_ENGINE=pdfium``. It covers **rendering only**; parsing still uses
PyMuPDF for now (a larger, separate effort). Activates only when pypdfium2 is importable.
"""

from __future__ import annotations

import io


def pdfium_available() -> bool:
    """True when pypdfium2 can be imported."""
    try:
        import pypdfium2  # noqa: F401
    except Exception:  # noqa: BLE001 - treat any import failure as "not available"
        return False
    return True


def rasterize_pages(
    data: bytes,
    page_indices: list[int],
    *,
    scale: float,
    max_side: int,
    cap: int,
) -> dict[int, bytes]:
    """Rasterise the requested pages to PNG bytes, mirroring the PyMuPDF rasteriser's contract.

    Renders at ``scale`` (pixels per point), down-scaling any page whose longest side would exceed
    ``max_side``. Out-of-range indices are skipped; at most ``cap`` pages are rendered.
    """
    import pypdfium2 as pdfium

    indices = [i for i in page_indices if i >= 0][:cap]
    pdf = pdfium.PdfDocument(data)
    out: dict[int, bytes] = {}
    try:
        count = len(pdf)
        for i in indices:
            if i >= count:
                continue
            page = pdf[i]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            if max_side and max(image.size) > max_side:
                ratio = max_side / float(max(image.size))
                bitmap = page.render(scale=scale * ratio)
                image = bitmap.to_pil()
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            out[i] = buf.getvalue()
    finally:
        pdf.close()
    return out
