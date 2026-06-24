"""Redaction is enforced on export — redacted text is removed, not hidden."""

from __future__ import annotations

import io

from docx import Document as DocxDocument

from docos.services.docengine.adapters.docx import _DOCX_MIME, DocxAdapter
from docos.services.docengine.adapters.txt import TxtAdapter


def _first_run(doc):
    return next(n for n in doc.nodes.values() if n.type == "run")


def test_txt_export_removes_redacted_run_text():
    doc = TxtAdapter().parse(b"public text\n\nSECRET DATA")
    secret = next(n for n in doc.nodes.values() if n.type == "run" and "SECRET" in n.text)
    doc.redaction.redacted_node_ids.append(secret.id)

    out = TxtAdapter().export(doc, target_mime="text/plain").decode()
    assert "SECRET DATA" not in out
    assert "public text" in out


def test_docx_export_removes_redacted_run_text(sample_docx_bytes):
    doc = DocxAdapter().parse(sample_docx_bytes)
    run = next(
        n for n in doc.nodes.values() if n.type == "run" and "normal paragraph" in (n.text or "")
    )
    doc.redaction.redacted_node_ids.append(run.id)

    out = DocxAdapter().export(doc, target_mime=_DOCX_MIME)
    reopened = DocxDocument(io.BytesIO(out))
    full_text = "\n".join(p.text for p in reopened.paragraphs)
    assert "normal paragraph" not in full_text


def test_ancestor_redaction_hides_child_runs():
    doc = TxtAdapter().parse(b"keep me\n\nhide this block")
    para = next(
        n
        for n in doc.nodes.values()
        if n.type == "paragraph" and any("hide" in (doc.nodes[c].text or "") for c in n.children)
    )
    doc.redaction.redacted_node_ids.append(para.id)  # redact the paragraph, not the run

    out = TxtAdapter().export(doc, target_mime="text/plain").decode()
    assert "hide this block" not in out
    assert "keep me" in out
