"""Send-Ready Check / Document X-Ray + one-shot "Clean Before You Send" endpoints.

``GET /readiness`` (read-only) answers "is this document safe and complete to send?" by
composing the existing detectors into a single verdict + per-check breakdown.

``POST /clean`` is the moat: it applies every auto-fixable issue the report found
(strip hidden metadata + true-redact exposed PII) as one reversible, audited patch, re-runs
the check, and returns the post-clean verdict together with a validation **proof** that the
removed text is unrecoverable from the exported copy. The clean file itself is downloaded via
the existing ``GET /export`` (which already carries the ``X-DocOS-Validation`` header).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.access import get_owned_document
from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.routes_export import _render_export, _signature_valid
from docos.api.schemas import CleanResponse, ReadinessResponse, RedactionAuditResponse
from docos.api.session import Actor, get_actor
from docos.deps import blob_store_dep, db_session, get_registry
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.docengine.registry import AdapterRegistry
from docos.services.provenance import readiness, redaction_audit, sensitive, validation
from docos.services.provenance.redaction_audit import RedactionAuditReport
from docos.settings import get_settings
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["readiness"])

# Source format → the format to export + validate the clean copy in (most faithful round-trip).
_NATIVE_EXPORT = {
    "pdf": "pdf",
    "docx": "docx",
    "pptx": "pptx",
    "xlsx": "xlsx",
    "txt": "txt",
    "md": "md",
    "html": "html",
}


def _native_export_format(source_format: str) -> str:
    return _NATIVE_EXPORT.get(source_format, "docx")


@router.get("/{doc_id}/readiness", response_model=ReadinessResponse)
def document_readiness(
    doc_id: str, session: Session = Depends(db_session), actor: Actor = Depends(get_actor)
) -> ReadinessResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    report = readiness.build_report(doc)
    return ReadinessResponse(doc_id=doc_id, report=report)


@router.get("/{doc_id}/redaction-audit", response_model=RedactionAuditResponse)
async def redaction_audit_endpoint(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> RedactionAuditResponse:
    """Un-Redact Test: is any text still recoverable under this PDF's 'redactions'?"""
    record = get_owned_document(session, doc_id, actor)
    if record.source_format != "pdf" or not record.blob_key:
        audit = RedactionAuditReport(
            is_pdf=False, summary="The un-redact test only applies to PDF files."
        )
    else:
        audit = redaction_audit.audit_pdf(
            await blob_store.get(record.blob_key), max_pages=get_settings().max_scan_pages
        )
    return RedactionAuditResponse(doc_id=doc_id, audit=audit)


@router.post("/{doc_id}/clean", response_model=CleanResponse)
async def clean_document(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> CleanResponse:
    """Apply the auto-fixable issues, re-check, and return the verdict + proof for the copy."""
    record, doc = _load_latest(session, doc_id, actor)
    report = readiness.build_report(doc)

    # Gather the auto-fixes the report flagged. Unfilled fields (need user input) and applying
    # pending redactions (happens at export) are intentionally not auto-fixed here.
    ops: list[Patch] = []
    needs_sanitize = any(
        c.id == "hidden_metadata" and c.status != "pass" for c in report.checks
    )
    if needs_sanitize:
        ops.append(Patch(op="sanitize_metadata"))
    for node_id in sensitive.redaction_node_ids(sensitive.scan_document(doc)):
        ops.append(Patch(op="redact", target_id=node_id))

    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent=f"clean before send: {len(ops)} fix(es)",
        created_at=datetime.now(UTC),
    )
    new_version_id, updated = apply_and_commit(
        session,
        doc_id,
        doc,
        patch,
        event="document.cleaned",
        detail={"fixes": len(ops)},
    )

    # Render + validate the clean copy in its native format to produce the proof.
    fmt = _native_export_format(record.source_format)
    data, _mime, _ext = await _render_export(updated, record, fmt, registry, blob_store)
    proof = validation.validate_export(
        updated, fmt, data, signature_valid=_signature_valid(updated)
    )

    return CleanResponse(
        doc_id=doc_id,
        applied=bool(ops),
        new_version_id=new_version_id,
        report=readiness.build_report(updated),
        validation=proof,
    )
