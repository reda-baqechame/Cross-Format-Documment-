"""Searchable-PDF generation over the API."""

from __future__ import annotations


def _pdf_text(data: bytes) -> str:
    import fitz

    pdf = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in pdf)
    pdf.close()
    return text


def test_born_digital_searchable_pdf_from_text(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("d.txt", b"Searchable heading\n\nA body paragraph.", "text/plain")},
    ).json()["doc_id"]

    res = client.get(f"/documents/{doc_id}/searchable-pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"
    # Text is real/selectable, not a flat image.
    assert "Searchable heading" in _pdf_text(res.content)
    assert "body paragraph" in _pdf_text(res.content)


def test_redacted_text_is_excluded(client):
    doc_id = client.post(
        "/documents",
        files={"file": ("d.txt", b"Public line.\n\nSECRET line.", "text/plain")},
    ).json()["doc_id"]
    nodes = client.get(f"/documents/{doc_id}/model").json()["document"]["nodes"]
    secret_run = next(
        nid for nid, n in nodes.items() if n["type"] == "run" and "SECRET" in (n.get("text") or "")
    )
    client.post(
        f"/documents/{doc_id}/patches",
        json={"ops": [{"op": "redact", "target_id": secret_run}]},
    )

    text = _pdf_text(client.get(f"/documents/{doc_id}/searchable-pdf").content)
    assert "Public line" in text
    assert "SECRET" not in text  # true removal carries through to the searchable PDF


def test_born_digital_pdf_skips_raster(client, sample_pdf_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("contract.pdf", sample_pdf_bytes, "application/pdf")}
    ).json()["doc_id"]

    res = client.get(f"/documents/{doc_id}/searchable-pdf")
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"
    # Born-digital PDFs should still expose extracted text without rasterizing every page.
    assert len(_pdf_text(res.content).strip()) > 0


def test_image_document_returns_valid_pdf(client, sample_image_bytes):
    doc_id = client.post(
        "/documents", files={"file": ("scan.png", sample_image_bytes, "image/png")}
    ).json()["doc_id"]

    res = client.get(f"/documents/{doc_id}/searchable-pdf")
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"
    import fitz

    pdf = fitz.open(stream=res.content, filetype="pdf")
    assert pdf.page_count == 1  # the scan becomes one searchable page
    pdf.close()
