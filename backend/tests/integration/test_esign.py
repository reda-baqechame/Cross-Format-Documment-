"""E-signature seam: honest integrity-seal default + a stubbed external-provider path."""

from __future__ import annotations

import io

import pytest

from docos.deps import get_signature_provider
from docos.services.esign import SignatureProvider, SignatureResult


def _upload_pdf(client, sample_pdf_bytes) -> str:
    return client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]


def test_default_signature_request_is_honest_seal(client, sample_pdf_bytes):
    doc_id = _upload_pdf(client, sample_pdf_bytes)
    res = client.post(
        f"/documents/{doc_id}/signature-request", json={"signers": [{"name": "Jane"}]}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "seal"
    assert body["status"] == "sealed"
    assert body["legally_binding"] is False  # never claims binding without a real provider
    assert "not a legally-binding" in body["detail"].lower()

    # The seal really applied — signature status reports signed.
    assert client.get(f"/documents/{doc_id}/signature").json()["signed"] is True


def test_signature_request_is_session_isolated(client, make_client, sample_pdf_bytes):
    doc_id = _upload_pdf(client, sample_pdf_bytes)
    rid = client.post(f"/documents/{doc_id}/signature-request", json={}).json()["id"]
    other = make_client()
    assert other.get(f"/signature-requests/{rid}").status_code == 404


def test_external_provider_path_with_stub(client, make_client, sample_pdf_bytes):
    """Inject a fake external provider via dependency override (no real HTTP)."""

    class _FakeProvider(SignatureProvider):
        name = "external"

        def create_request(self, *, document, filename, signers, subject) -> SignatureResult:
            assert document  # the route rendered + passed the PDF bytes
            return SignatureResult(
                provider="external", status="sent", external_id="ext-123",
                signing_url="https://sign.example/x", detail="sent", legally_binding=True,
            )

        def status(self, external_id) -> SignatureResult:
            return SignatureResult(
                provider="external", status="completed", external_id=external_id,
                legally_binding=True,
            )

    client.app.dependency_overrides[get_signature_provider] = lambda: _FakeProvider()
    try:
        doc_id = _upload_pdf(client, sample_pdf_bytes)
        res = client.post(
            f"/documents/{doc_id}/signature-request",
            json={"signers": [{"name": "Jane", "email": "jane@example.com"}], "subject": "NDA"},
        ).json()
        assert res["provider"] == "external"
        assert res["status"] == "sent"
        assert res["signing_url"] == "https://sign.example/x"
        assert res["legally_binding"] is True

        status = client.get(f"/signature-requests/{res['id']}").json()
        assert status["status"] == "completed"  # refreshed from the provider
    finally:
        client.app.dependency_overrides.pop(get_signature_provider, None)


def test_webhook_requires_configured_provider(client):
    assert client.post("/esign/webhook", content=b"{}").status_code == 501


@pytest.mark.parametrize("payload", [b'{"id":"x","status":"completed"}'])
def test_webhook_signature_is_verified(payload):
    from docos.services.esign import verify_webhook

    secret = "wh-secret"
    import hashlib
    import hmac

    good = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_webhook(payload, good, secret) is True
    assert verify_webhook(payload, "deadbeef", secret) is False
