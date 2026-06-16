"""Metadata sanitization flips the health panel's metadata risk."""

from __future__ import annotations

from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.provenance.health import compute_health
from docos.services.provenance.service import ProvenancePolicyServiceImpl
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def _doc_with_risky_meta():
    doc = TxtAdapter().parse(b"some body text")
    doc.meta.custom = {"author": "Alice", "last_modified_by": "Bob"}
    return doc


def test_sanitize_metadata_flips_health_risk():
    doc = _doc_with_risky_meta()
    assert compute_health(doc).metadata_risk is True

    service = ProvenancePolicyServiceImpl(session=None)  # sanitize_metadata needs no session
    orch = SemanticOrchestratorImpl(LocalNoopClient())

    patch = service.sanitize_metadata(doc)
    updated = orch.apply(doc, patch)

    assert compute_health(updated).metadata_risk is False
    assert "author" not in updated.meta.custom


def test_sanitize_metadata_is_reversible():
    doc = _doc_with_risky_meta()
    service = ProvenancePolicyServiceImpl(session=None)
    orch = SemanticOrchestratorImpl(LocalNoopClient())

    patch = service.sanitize_metadata(doc)
    updated = orch.apply(doc, patch)
    reverted = orch.revert(updated, patch)

    assert reverted.meta.custom.get("author") == "Alice"
    assert compute_health(reverted).metadata_risk is True
