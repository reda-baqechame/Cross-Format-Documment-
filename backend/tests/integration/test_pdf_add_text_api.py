"""The add_node→export round-trip the UI uses to place new text on a PDF page.

`addPositionedText` in the web client posts an ``add_node`` patch with a bbox-carrying run
parented under the page node; ``write_back_pdf`` then inserts it at that location. This proves
the API path (not just the model-level writer) lands the text in the exported PDF.
"""

from __future__ import annotations

import io

import fitz


def test_positioned_text_patch_lands_in_export(client, sample_pdf_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]

    nodes = client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"]
    page_id = next(nid for nid, n in nodes.items() if n["type"] == "page")

    block = {"id": "p_added", "type": "paragraph", "parent_id": page_id, "children": ["run_added"]}
    run = {
        "id": "run_added",
        "type": "run",
        "parent_id": "p_added",
        "text": "UI ADDED TEXT",
        "bbox": {"x0": 72, "y0": 240, "x1": 320, "y1": 258},
        "size": 12,
    }
    res = client.post(
        f"/documents/{doc_id}/patches",
        json={
            "ops": [
                {
                    "op": "add_node",
                    "payload": {"node": block, "nodes": [block, run], "parent_id": page_id},
                }
            ]
        },
    )
    assert res.status_code == 200

    out = client.get(f"/documents/{doc_id}/export?format=pdf")
    assert out.status_code == 200
    pdf = fitz.open(stream=out.content, filetype="pdf")
    try:
        text = "\n".join(p.get_text() for p in pdf)
    finally:
        pdf.close()
    assert "UI ADDED TEXT" in text  # the UI-placed run reached the PDF
    assert "Hello PDF world" in text  # original content untouched
