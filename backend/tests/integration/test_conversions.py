"""Any-format → Markdown / HTML / CSV export over the canonical model."""

from __future__ import annotations

import io


def test_export_docx_as_markdown_and_html(client, sample_docx_bytes):
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    doc_id = client.post(
        "/documents", files={"file": ("d.docx", io.BytesIO(sample_docx_bytes), docx_mime)}
    ).json()["doc_id"]

    md = client.get(f"/documents/{doc_id}/export", params={"format": "md"})
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    body = md.content.decode()
    assert "# A Heading" in body  # heading became an ATX heading
    assert "A normal paragraph with text." in body

    html = client.get(f"/documents/{doc_id}/export", params={"format": "html"})
    assert html.status_code == 200
    assert "<h1>A Heading</h1>" in html.content.decode()


def test_export_txt_doc_as_csv_rows(client):
    doc_id = client.post(
        "/documents", files={"file": ("d.txt", b"Line one\n\nLine two", "text/plain")}
    ).json()["doc_id"]
    csv_out = client.get(f"/documents/{doc_id}/export", params={"format": "csv"})
    assert csv_out.status_code == 200
    assert csv_out.headers["content-type"].startswith("text/csv")
    rows = csv_out.content.decode().splitlines()
    assert "Line one" in rows[0]


def test_redaction_honored_in_markdown(client):
    doc_id = client.post(
        "/documents", files={"file": ("d.txt", b"keep this\n\nsecret line", "text/plain")}
    ).json()["doc_id"]
    model = client.get(f"/documents/{doc_id}/model").json()["document"]
    secret = next(n["id"] for n in model["nodes"].values() if n.get("text") == "secret line")
    client.post(
        f"/documents/{doc_id}/patches", json={"ops": [{"op": "redact", "target_id": secret}]}
    )

    md = client.get(f"/documents/{doc_id}/export", params={"format": "md"}).content.decode()
    assert "keep this" in md
    assert "secret line" not in md


def test_unknown_format_rejected(client):
    doc_id = client.post("/documents", files={"file": ("d.txt", b"hi", "text/plain")}).json()[
        "doc_id"
    ]
    assert client.get(f"/documents/{doc_id}/export", params={"format": "xyz"}).status_code == 400
