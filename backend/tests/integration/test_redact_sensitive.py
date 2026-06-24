"""End-to-end: detect sensitive data, one-click redact, and confirm true removal on export."""

from __future__ import annotations


def _upload(client, text: str) -> str:
    return client.post("/documents", files={"file": ("d.txt", text.encode(), "text/plain")}).json()[
        "doc_id"
    ]


def test_scan_then_redact_removes_pii_from_export(client):
    doc_id = _upload(
        client,
        "Contact jane@example.com for details.\n\n"
        "My SSN is 123-45-6789.\n\n"
        "This paragraph is perfectly clean.",
    )

    scan = client.get(f"/documents/{doc_id}/sensitive").json()
    assert scan["summary"].get("email") == 1
    assert scan["summary"].get("us_ssn") == 1
    assert scan["node_count"] == 2

    res = client.post(f"/documents/{doc_id}/redact-sensitive").json()
    assert res["applied"] is True
    assert res["new_version_id"]

    out = client.get(f"/documents/{doc_id}/export", params={"format": "txt"})
    assert out.status_code == 200
    text = out.content.decode()
    assert "jane@example.com" not in text  # truly removed
    assert "123-45-6789" not in text
    assert "perfectly clean" in text  # untouched content survives

    # Re-scanning finds nothing — the redacted nodes are skipped.
    assert client.get(f"/documents/{doc_id}/sensitive").json()["node_count"] == 0


def test_redact_sensitive_is_a_noop_when_clean(client):
    doc_id = _upload(client, "Nothing sensitive here at all.")
    res = client.post(f"/documents/{doc_id}/redact-sensitive").json()
    assert res["applied"] is False
    assert res["new_version_id"] is None
