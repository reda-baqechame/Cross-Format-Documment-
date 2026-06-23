"""DRM seam: honest 501 by default, applies the provider when configured."""

from __future__ import annotations

import io

from docos.deps import get_drm_provider
from docos.services.drm import DrmProvider


def _upload_pdf(client, sample_pdf_bytes) -> str:
    return client.post(
        "/documents", files={"file": ("d.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    ).json()["doc_id"]


def test_drm_501_when_not_configured(client, sample_pdf_bytes):
    doc_id = _upload_pdf(client, sample_pdf_bytes)
    res = client.post(f"/documents/{doc_id}/drm")
    assert res.status_code == 501
    detail = res.json()["detail"].lower()
    assert "drm is not configured" in detail
    assert "protect pdf" in detail  # points to the honest local alternative


def test_drm_applies_provider_when_configured(client, sample_pdf_bytes):
    class _FakeDrm(DrmProvider):
        name = "external"

        def apply(self, data, mime, *, policy=None):
            assert data[:4] == b"%PDF"  # got the rendered PDF
            return b"DRM-WRAPPED", "application/pdf"

    client.app.dependency_overrides[get_drm_provider] = lambda: _FakeDrm()
    try:
        doc_id = _upload_pdf(client, sample_pdf_bytes)
        res = client.post(f"/documents/{doc_id}/drm")
        assert res.status_code == 200
        assert res.content == b"DRM-WRAPPED"
        assert "attachment" in res.headers["content-disposition"]
    finally:
        client.app.dependency_overrides.pop(get_drm_provider, None)


def test_drm_provider_none_by_default():
    assert get_drm_provider() is None
