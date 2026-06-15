"""PDF write-back for redactions.

Faithful PDF *editing* is a large effort, but the trust-critical case — truly
removing redacted content from a PDF — is tractable: we reopen the original PDF and,
for every redacted run that carries a bounding box, burn a PyMuPDF redaction over its
rectangle and apply it (which deletes the underlying text and image data, not just
covers it). Non-redaction edits are not reflected here; download as DOCX for those.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted


def _page_number_of(doc: CanonicalDocument, node_id: str | None) -> int | None:
    """Walk ancestors to the enclosing page and return its 1-based page number."""
    seen: set[str] = set()
    current = node_id
    while current and current not in seen:
        node = doc.nodes.get(current)
        if node is None:
            return None
        if node.type == "page":
            return getattr(node, "page_number", None)
        seen.add(current)
        current = node.parent_id
    return None


def apply_redactions_to_pdf(data: bytes, doc: CanonicalDocument) -> bytes:
    """Return the original PDF with every redacted run's region truly removed."""
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        touched: set[int] = set()
        for node in doc.nodes.values():
            if node.type != "run" or node.bbox is None:
                continue
            if not is_redacted(doc, node.id):
                continue
            pno = _page_number_of(doc, node.id)
            if pno is None or not (1 <= pno <= pdf.page_count):
                continue
            page = pdf[pno - 1]
            b = node.bbox
            page.add_redact_annot(fitz.Rect(b.x0, b.y0, b.x1, b.y1), fill=(0, 0, 0))
            touched.add(pno - 1)

        for index in touched:
            pdf[index].apply_redactions()

        return pdf.tobytes()
    finally:
        pdf.close()
