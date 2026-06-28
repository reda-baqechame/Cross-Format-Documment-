"""Engine + license registry — the governance/firewall layer."""

from __future__ import annotations

from docos.services.engines import registry


def test_every_engine_has_a_valid_license_class():
    valid = {
        "safe_core",
        "safe_with_conditions",
        "external_service_only",
        "commercial_required",
        "avoid",
    }
    for e in registry.REGISTRY:
        assert e.license_class in valid, f"{e.name} has invalid class {e.license_class}"
        assert e.spdx, f"{e.name} missing SPDX"
        assert e.capabilities, f"{e.name} declares no capabilities"


def test_report_marks_installed_engines_with_versions():
    report = {r["name"]: r for r in registry.registry_report()}
    # pypdf is a core dependency — installed with a version here.
    assert report["pypdf"]["installed"] is True
    assert report["pypdf"]["version"]
    # qwen2.5-vl is a model seam, not pip-installed in this env.
    assert report["qwen2.5-vl"]["installed"] is False


def test_firewall_allows_only_documented_avoid_exceptions():
    # pymupdf is AGPL ("avoid") and installed, but it is a tracked EXCEPTION (migration in flight),
    # so the firewall must NOT flag it; nothing else forbidden should be installed.
    forbidden = dict(registry.forbidden_installed())
    assert "pymupdf" not in forbidden  # documented exception
    assert forbidden == {}, f"unexpected forbidden engines installed: {forbidden}"


def test_pymupdf_is_classified_avoid_with_an_exception():
    assert registry.engine("pymupdf").license_class == "avoid"
    assert "pymupdf" in registry.EXCEPTIONS


def test_onlyoffice_is_external_service_only():
    # AGPL office suite must never be core — only an external service.
    assert registry.engine("onlyoffice").license_class == "external_service_only"
