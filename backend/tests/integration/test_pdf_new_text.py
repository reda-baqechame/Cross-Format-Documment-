"""PDF write-back: a new model run that carries a bbox is placed into the exported PDF."""

from __future__ import annotations

import fitz

from docos.model.geometry import BBox
from docos.model.ids import new_node_id
from docos.model.nodes import ParagraphNode, RunNode
from docos.services.docengine.adapters.pdf import PdfAdapter
from docos.services.docengine.writers.pdf_writer import write_back_pdf


def test_positioned_new_text_is_written_into_pdf(sample_pdf_bytes):
    doc = PdfAdapter().parse(sample_pdf_bytes)
    page = next(n for n in doc.nodes.values() if n.type == "page")

    para = ParagraphNode(id=new_node_id(), parent_id=page.id, reading_order=99)
    run = RunNode(
        id=new_node_id(),
        parent_id=para.id,
        text="ADDED ANNOTATION",
        bbox=BBox(x0=72, y0=200, x1=320, y1=220),
        size=12.0,
    )
    para.children.append(run.id)
    page.children.append(para.id)
    doc.add_node(para)
    doc.add_node(run)

    out = write_back_pdf(sample_pdf_bytes, doc)
    pdf = fitz.open(stream=out, filetype="pdf")
    try:
        text = "\n".join(p.get_text() for p in pdf)
    finally:
        pdf.close()
    assert "ADDED ANNOTATION" in text  # new positioned text landed
    assert "Second line of text" in text  # untouched original survives
