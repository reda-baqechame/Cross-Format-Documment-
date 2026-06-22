"""Send-Ready Check / Document X-Ray: verdict roll-up and per-check behaviour."""

from __future__ import annotations

from datetime import UTC, datetime

from docos.model.document import CanonicalDocument, DocumentMeta
from docos.model.nodes import FieldNode, ParagraphNode, RootNode, RunNode
from docos.services.provenance import readiness


def _doc(texts: list[str]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id="root")
    doc = CanonicalDocument(
        doc_id="d1",
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt",
            source_mime="text/plain",
            created_at=now,
            modified_at=now,
            page_count=1,
        ),
    )
    doc.add_node(root)
    for i, t in enumerate(texts):
        para = ParagraphNode(id=f"p{i}", parent_id=root.id, reading_order=i)
        run = RunNode(id=f"r{i}", parent_id=para.id, text=t)
        para.children.append(run.id)
        root.children.append(para.id)
        doc.add_node(para)
        doc.add_node(run)
    return doc


def _check(report: readiness.ReadinessReport, check_id: str) -> readiness.ReadinessCheck:
    return next(c for c in report.checks if c.id == check_id)


def test_clean_document_is_ready():
    report = readiness.build_report(_doc(["A perfectly ordinary sentence."]))
    assert report.verdict == "ready"
    assert all(c.status == "pass" for c in report.checks)


def test_exposed_pii_flags_needs_fixes_with_redact_fix():
    report = readiness.build_report(_doc(["Reach me at jane@example.com or 415-555-2671."]))
    assert report.verdict == "needs_fixes"
    pii = _check(report, "exposed_pii")
    assert pii.status == "warn"
    assert pii.count == 2
    assert pii.fixable and pii.fix_action == readiness.FIX_REDACT_PII
    # The detail must never echo a raw detected value.
    assert "jane@example.com" not in pii.detail


def test_pending_redaction_blocks():
    doc = _doc(["secret@example.com"])
    doc.redaction.pending.append("r0")
    report = readiness.build_report(doc)
    assert report.verdict == "blocked"
    pending = _check(report, "pending_redactions")
    assert pending.status == "fail"
    assert pending.fix_action == readiness.FIX_APPLY_REDACTIONS


def test_hidden_metadata_warns_with_sanitize_fix():
    doc = _doc(["Clean text."])
    doc.meta.custom["author"] = "Jane Doe"
    report = readiness.build_report(doc)
    meta = _check(report, "hidden_metadata")
    assert meta.status == "warn"
    assert meta.fix_action == readiness.FIX_SANITIZE_METADATA
    assert report.verdict == "needs_fixes"


def test_unfilled_required_field_warns_but_is_not_auto_fixable():
    doc = _doc(["Form:"])
    doc.add_node(
        FieldNode(id="f0", parent_id="p0", field_name="Name", required=True, value=None)
    )
    doc.nodes["p0"].children.append("f0")
    report = readiness.build_report(doc)
    field = _check(report, "unfilled_fields")
    assert field.status == "warn"
    assert field.count == 1
    assert field.fixable is False
    assert report.verdict == "needs_fixes"


def test_blocked_outranks_warn():
    doc = _doc(["jane@example.com"])
    doc.redaction.pending.append("r0")
    doc.meta.custom["author"] = "Jane Doe"
    report = readiness.build_report(doc)
    assert report.verdict == "blocked"  # fail outranks the warnings
