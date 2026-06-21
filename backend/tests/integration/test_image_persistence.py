"""Images extracted at upload are persisted and embedded in exports (not placeholders)."""

from __future__ import annotations

import io

import fitz
from docx import Document as DocxDocument
from PIL import Image


def _png_bytes(color: tuple[int, int, int] = (10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "PNG")
    return buf.getvalue()


def _pdf_with_image() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((50, 50), "Has an image below", fontsize=14)
    page.insert_image(fitz.Rect(50, 80, 180, 210), stream=_png_bytes())
    data = doc.tobytes()
    doc.close()
    return data


def test_uploaded_pdf_image_is_embedded_in_docx_export(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("img.pdf", io.BytesIO(_pdf_with_image()), "application/pdf")},
    ).json()["doc_id"]

    # The model should carry a persisted image node (bytes written to blob storage at upload).
    model = client.get(f"/documents/{doc_id}/model").json()
    images = [n for n in model["document"]["nodes"].values() if n["type"] == "image"]
    assert images, "expected the PDF's image to be parsed into the model"
    assert any(n["attrs"].get("persisted") for n in images)

    # Exporting to DOCX embeds the real picture instead of a "[image: …]" placeholder.
    res = client.get(f"/documents/{doc_id}/export", params={"format": "docx"})
    assert res.status_code == 200
    rendered = DocxDocument(io.BytesIO(res.content))
    assert len(rendered.inline_shapes) >= 1
