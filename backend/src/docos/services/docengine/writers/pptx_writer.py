"""Universal canonical-model → PPTX writer.

Rebuilds a real ``.pptx`` from the node graph. If the document already has page
nodes (a PPTX or PDF origin), each page becomes one slide. Otherwise the document
is sectioned into slides by heading — each heading starts a new slide whose body
gathers the following paragraphs/lists — so a TXT or DOCX can be downloaded as a
deck. Tolerant by design: unknown nodes are skipped rather than raising.
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.util import Inches, Pt

from docos.model.document import CanonicalDocument
from docos.model.nodes import AnyNode
from docos.services.docengine.writers.redaction import run_text

_BLANK_LAYOUT = 6  # the standard blank layout in the default template


def _block_text(doc: CanonicalDocument, block: AnyNode) -> str:
    return "".join(run_text(doc, r) for r in doc.children_of(block.id) if r.type == "run")


def _table_lines(doc: CanonicalDocument, tnode: AnyNode) -> list[str]:
    lines: list[str] = []
    for row in doc.children_of(tnode.id):
        if row.type != "table_row":
            continue
        cells = [_block_text(doc, c) for c in doc.children_of(row.id) if c.type == "table_cell"]
        lines.append(" | ".join(cells))
    return lines


def _add_slide(prs: Presentation, title: str, body_lines: list[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[_BLANK_LAYOUT])
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(6.5))
    tf = box.text_frame
    tf.word_wrap = True
    first = tf.paragraphs[0]
    first.text = title or ""
    first.font.size = Pt(28)
    first.font.bold = True
    for line in body_lines:
        p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(16)


def model_to_pptx(doc: CanonicalDocument) -> bytes:
    prs = Presentation()
    top = doc.children_of(doc.root_id)
    pages = [n for n in top if n.type == "page"]

    if pages:
        for page in pages:
            title = ""
            body: list[str] = []
            for child in doc.children_of(page.id):
                if child.type == "heading" and not title:
                    title = _block_text(doc, child)
                elif child.type in ("paragraph", "heading"):
                    text = _block_text(doc, child)
                    if text:
                        body.append(text)
                elif child.type == "list":
                    for item in doc.children_of(child.id):
                        if item.type == "list_item":
                            body.append(f"• {_block_text(doc, item)}")
                elif child.type == "table":
                    body.extend(_table_lines(doc, child))
                elif child.type == "image":
                    body.append(f"[image: {getattr(child, 'alt_text', None) or 'image'}]")
            _add_slide(prs, title or f"Slide {page.page_number}", body)
    else:
        # Section a flat document into slides by heading.
        title = doc.meta.title or "Slide 1"
        body = []
        opened = False
        for node in top:
            if node.type == "heading":
                if opened or body:
                    _add_slide(prs, title, body)
                title = _block_text(doc, node) or "Slide"
                body = []
                opened = True
            elif node.type in ("paragraph", "list_item"):
                text = _block_text(doc, node)
                if text:
                    body.append(text)
            elif node.type == "list":
                for item in doc.children_of(node.id):
                    if item.type == "list_item":
                        body.append(f"• {_block_text(doc, item)}")
            elif node.type == "table":
                body.extend(_table_lines(doc, node))
        _add_slide(prs, title, body)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
