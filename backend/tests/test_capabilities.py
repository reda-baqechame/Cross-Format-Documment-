"""Tests for ``GET /capabilities`` — the truth-ledger endpoint.

These pin the honesty contract: every health flag maps to a capability, provider-gated
capabilities are reported as such when their env is unset, verified capabilities cite a proof,
and the AGPL PyMuPDF risk is surfaced.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from docos.main import create_app
from docos.settings import get_settings


def _caps(client: TestClient) -> dict:
    r = client.get("/capabilities")
    assert r.status_code == 200, r.text
    return r.json()


def _by_id(caps: dict, cid: str) -> dict:
    for c in caps["capabilities"]:
        if c["id"] == cid:
            return c
    raise AssertionError(f"capability {cid!r} not present")


def test_capabilities_returns_all_state_fields():
    with TestClient(create_app()) as client:
        data = _caps(client)
    assert "generated_at" in data
    assert "privacy_mode" in data
    assert "database" in data
    assert isinstance(data["capabilities"], list) and data["capabilities"]
    assert isinstance(data["engine_versions"], dict)
    assert isinstance(data["licence_risks"], list)
    for cap in data["capabilities"]:
        for field in (
            "id",
            "name",
            "state",
            "engine",
            "engine_version",
            "limitations",
            "last_verified_at",
            "proof_id",
            "warnings",
        ):
            assert field in cap, f"{cap['id']} missing {field}"


def test_valid_state_vocabulary_only():
    allowed = {
        "verified", "degraded", "provider_gated", "disabled", "broken", "claim_without_proof",
    }
    with TestClient(create_app()) as client:
        data = _caps(client)
    for cap in data["capabilities"]:
        assert cap["state"] in allowed, f"{cap['id']} has invalid state {cap['state']!r}"


def test_verified_capability_carries_proof_id():
    """A 'verified' capability (except collaboration, which is presence-only) must cite a proof."""
    with TestClient(create_app()) as client:
        data = _caps(client)
    for cap in data["capabilities"]:
        if cap["state"] == "verified" and cap["id"] != "collaboration":
            assert cap["proof_id"], f"{cap['id']} is verified but has no proof_id"


def test_provider_gated_when_env_unset():
    """When no provider credentials are configured, gated capabilities report provider_gated."""
    with TestClient(create_app()) as client:
        data = _caps(client)
    # Default dev settings: every external provider is unset.
    for cid in ("ai_ask_summarize", "ai_edit", "tts", "esign", "drm", "billing"):
        cap = _by_id(data, cid)
        assert cap["state"] == "provider_gated", (
            f"{cid} should be provider_gated, got {cap['state']}"
        )
        # And it must explain why (non-empty limitations) so the UI shows an honest reason.
        assert cap["limitations"], f"{cid} provider_gated with no limitations explanation"


def test_malware_scan_verified_by_default_offline():
    """The default offline scanner is the heuristic content-defense, not noop — so public
    uploads are inspected and the capability reports 'verified' (a release-blocker fix)."""
    with TestClient(create_app()) as client:
        data = _caps(client)
    cap = _by_id(data, "malware_scan")
    assert cap["state"] == "verified", f"malware_scan should be verified, got {cap['state']}"
    assert cap["engine"] == "scanner:heuristic"
    assert cap["proof_id"], "verified scanner must cite a proof"
    assert cap["limitations"], "scanner must honestly state it is not signature AV"


def test_agpl_pymupdf_risk_is_surfaced():
    """When PyMuPDF is installed (the AGPL blocker), the licence risk list is non-empty."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        version("pymupdf")
        pymupdf_installed = True
    except PackageNotFoundError:
        pymupdf_installed = False

    with TestClient(create_app()) as client:
        data = _caps(client)
    if pymupdf_installed:
        assert any("AGPL" in risk or "pymupdf" in risk.lower() for risk in data["licence_risks"]), (
            "PyMuPDF is installed but no AGPL risk was surfaced"
        )
        # And the PDF capabilities that still depend on it carry the warning.
        pdf_warn_caps = [
            c for c in data["capabilities"] if c["engine"].startswith(("pymupdf", "pdf-render"))
        ]
        assert pdf_warn_caps, "expected at least one PyMuPDF-backed PDF capability"
        for c in pdf_warn_caps:
            assert any("AGPL" in w for w in c["warnings"]), f"{c['id']} missing AGPL warning"


def test_search_is_honestly_relabeled_not_semantic():
    """The search capability must NOT claim semantic search until a recall benchmark proves it."""
    with TestClient(create_app()) as client:
        data = _caps(client)
    search = _by_id(data, "search")
    # It is either claim_without_proof (default, no benchmark) or verified — never pretending.
    assert search["state"] != "verified" or "keyword" in search["engine"]
    # And its limitations must call out the synonym/semantic gap honestly.
    joined = " ".join(search["limitations"]).lower()
    assert "semantic" in joined or "synonym" in joined or "keyword" in joined, (
        "search limitations do not honestly disclose the lexical/semantic gap: "
        f"{search['limitations']}"
    )


def test_health_flags_have_capability_counterparts():
    """Every /health boolean flag must map to a capability, so the two views stay consistent."""
    with TestClient(create_app()) as client:
        caps = _caps(client)
        health = client.get("/health").json()

    settings = get_settings()
    # The health-derived flags and the capability states must agree on the live config.
    pairs = [
        ("ai_enabled", "ai_ask_summarize", settings.ai_enabled),
        ("esign_configured", "esign", settings.esign_configured),
        ("tts_configured", "tts", settings.tts_configured),
        ("drm_configured", "drm", settings.drm_configured),
        ("billing_configured", "billing", settings.billing_configured),
    ]
    cap_by_id = {c["id"]: c for c in caps["capabilities"]}
    for health_key, cap_id, configured in pairs:
        assert health[health_key] is configured, f"/health {health_key} disagrees with settings"
        cap = cap_by_id[cap_id]
        if configured:
            assert cap["state"] == "verified", f"{cap_id} should be verified when configured"
        else:
            assert cap["state"] == "provider_gated", f"{cap_id} should be provider_gated when unset"


def test_pdf_engine_version_reported_from_runtime():
    """The engine_version reflects what is actually importable, not what's declared in pyproject."""
    from importlib.metadata import PackageNotFoundError, version

    with TestClient(create_app()) as client:
        data = _caps(client)
    pdf_organize = _by_id(data, "pdf_organize")
    try:
        expected = version("pymupdf")
    except PackageNotFoundError:
        expected = None
    assert pdf_organize["engine_version"] == expected
