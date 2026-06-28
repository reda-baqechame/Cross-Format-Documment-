"""Reusable redaction proof: build a document with a known secret, redact it, export to every
from-model format, and scan the exported bytes — including decompressed OOXML zip parts — for any
recoverable occurrence of the secret. This is the executable form of the release gate
"redaction: zero recoverable target strings in exported bytes".
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.ids import new_doc_id, new_node_id
from docos.model.nodes import (
    HeadingNode,
    ImageNode,
    ParagraphNode,
    RootNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.services.docengine.writers.docx_writer import model_to_docx
from docos.services.docengine.writers.markup import (
    model_to_csv,
    model_to_html,
    model_to_markdown,
    model_to_rtf,
)
from docos.services.docengine.writers.pptx_writer import model_to_pptx
from docos.services.docengine.writers.xlsx_writer import model_to_xlsx

SECRET = "TOPSECRET-9F3X-ZZ"
# A non-redacted control: it MUST survive export (proves we don't nuke everything) and proves the
# scanner can actually find a present string (so a "clean" verdict on the secret is meaningful).
CONTROL = "publicvisiblemarker42"

# (format label, writer). PDF export is a write-back over original bytes (fitz path / Phase C),
# audited separately by redaction_audit; these are the from-model writers.
WRITERS = [
    ("docx", model_to_docx),
    ("xlsx", model_to_xlsx),
    ("pptx", model_to_pptx),
    ("html", model_to_html),
    ("markdown", model_to_markdown),
    ("rtf", model_to_rtf),
    ("csv", model_to_csv),
]


@dataclass(frozen=True)
class FormatResult:
    fmt: str
    secret_locations: list[str]  # where the secret leaked (empty = clean)
    control_present: bool  # the non-redacted marker survived


def build_redacted_document() -> CanonicalDocument:
    """A document with the secret in a heading, paragraph, table cell, and image alt-text — all
    redacted — plus a non-redacted control paragraph that must survive."""
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    redact: list[str] = []

    heading = HeadingNode(id=new_node_id(), parent_id=root.id, level=1, reading_order=0)
    hrun = RunNode(id=new_node_id(), parent_id=heading.id, text=SECRET)
    heading.children.append(hrun.id)
    root.children.append(heading.id)
    doc.add_node(heading)
    doc.add_node(hrun)
    redact.append(heading.id)

    para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=1)
    prun = RunNode(id=new_node_id(), parent_id=para.id, text=f"contact {SECRET} immediately")
    para.children.append(prun.id)
    root.children.append(para.id)
    doc.add_node(para)
    doc.add_node(prun)
    redact.append(para.id)

    # Two-row table: row 0 holds the secret (redacted); row 1 holds the control (kept). This keeps
    # the control present even in tables-only formats like CSV, so the proof is meaningful there.
    table = TableNode(id=new_node_id(), parent_id=root.id, reading_order=2, rows=2, cols=1)
    s_row = TableRowNode(id=new_node_id(), parent_id=table.id, row=0, reading_order=0)
    s_cell = TableCellNode(id=new_node_id(), parent_id=s_row.id, row=0, col=0, reading_order=0)
    s_run = RunNode(id=new_node_id(), parent_id=s_cell.id, text=SECRET)
    s_cell.children.append(s_run.id)
    s_row.children.append(s_cell.id)
    c_row = TableRowNode(id=new_node_id(), parent_id=table.id, row=1, reading_order=1)
    c_cell = TableCellNode(id=new_node_id(), parent_id=c_row.id, row=1, col=0, reading_order=0)
    c_run = RunNode(id=new_node_id(), parent_id=c_cell.id, text=CONTROL)
    c_cell.children.append(c_run.id)
    c_row.children.append(c_cell.id)
    table.children.extend([s_row.id, c_row.id])
    root.children.append(table.id)
    for node in (table, s_row, s_cell, s_run, c_row, c_cell, c_run):
        doc.add_node(node)
    redact.append(s_cell.id)

    image = ImageNode(
        id=new_node_id("img"),
        parent_id=root.id,
        reading_order=3,
        blob_ref="x",
        mime="image/png",
        alt_text=SECRET,
    )
    root.children.append(image.id)
    doc.add_node(image)
    redact.append(image.id)

    # Non-redacted control paragraph — must survive every export.
    survivor = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=4)
    srun = RunNode(id=new_node_id(), parent_id=survivor.id, text=f"keep {CONTROL} please")
    survivor.children.append(srun.id)
    root.children.append(survivor.id)
    doc.add_node(survivor)
    doc.add_node(srun)

    doc.redaction.redacted_node_ids = redact
    return doc


def _find(data: bytes, needle: str) -> list[str]:
    """Where ``needle`` occurs in ``data`` — raw bytes and every zip entry (OOXML parts)."""
    hits: list[str] = []
    raw = needle.encode()
    if raw in data:
        hits.append("raw-bytes")
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for entry in zf.namelist():
                    if raw in zf.read(entry):
                        hits.append(f"zip:{entry}")
        except zipfile.BadZipFile:
            hits.append("corrupt-zip")
    return hits


def _find_pdf(data: bytes, needle: str) -> list[str]:
    """Where ``needle`` occurs in a PDF — raw bytes, extracted text, and decompressed streams."""
    hits: list[str] = []
    raw = needle.encode()
    if raw in data:
        hits.append("raw-bytes")
    # Text objects (visible + invisible render-mode-3) via the permissive engine.
    from docos.services.docengine import pdfium

    if needle in pdfium.extract_text(data):
        hits.append("text-layer")
    # Decompressed content streams (catches a secret hiding in a compressed stream).
    try:
        import pikepdf

        with pikepdf.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                contents = page.get("/Contents")
                streams = contents if isinstance(contents, list) else [contents]
                for stream in streams:
                    if stream is not None and raw in bytes(stream.read_bytes()):
                        hits.append("content-stream")
                        break
    except Exception:  # noqa: BLE001 - stream walk is best-effort; raw+text already cover the gate
        pass
    return hits


def build_pdf_and_redact() -> bytes:
    """Born-digital PDF with the secret + control, parsed, the secret run redacted, written back.

    Exercises the real PDF export path (parse -> redact -> write_back_pdf), so the proof covers
    the write-back redaction, not just the from-model writers.
    """
    from reportlab.pdfgen import canvas

    from docos.services.docengine.adapters.pdf import PdfAdapter
    from docos.services.docengine.writers.pdf_writer import write_back_pdf

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(595.0, 842.0))
    pdf.drawString(72, 760, "Public heading visible")
    pdf.drawString(72, 730, f"{SECRET} confidential")
    pdf.drawString(72, 700, f"keep {CONTROL} please")
    pdf.save()
    source = buf.getvalue()

    doc = PdfAdapter().parse(source)
    secret_runs = [
        n.id
        for n in doc.nodes.values()
        if n.type == "run" and SECRET in (getattr(n, "text", "") or "")
    ]
    doc.redaction.redacted_node_ids = secret_runs
    return write_back_pdf(source, doc)


def run() -> list[FormatResult]:
    doc = build_redacted_document()
    results: list[FormatResult] = []
    for fmt, writer in WRITERS:
        data = writer(doc)
        results.append(
            FormatResult(
                fmt=fmt,
                secret_locations=_find(data, SECRET),
                control_present=bool(_find(data, CONTROL)),
            )
        )
    pdf_bytes = build_pdf_and_redact()
    results.append(
        FormatResult(
            fmt="pdf",
            secret_locations=_find_pdf(pdf_bytes, SECRET),
            control_present=bool(_find_pdf(pdf_bytes, CONTROL)),
        )
    )
    return results
