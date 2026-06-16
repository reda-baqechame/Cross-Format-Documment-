"""Patch endpoint — the single "mutate the document" entry point.

Accepts either a natural-language ``instruction`` (routed through the LLM, a no-op
with the offline client) or an explicit list of deterministic ``ops`` (set_text,
update_node, retag, redact, …). In both cases the resulting reversible patch flows
through the same apply → commit_version → audit path, so every edit is versioned and
undoable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import (
    PatchRequest,
    PatchResponse,
    SensitiveScanResponse,
    SignatureResponse,
    SignRequest,
)
from docos.db.models import Document
from docos.deps import db_session, get_orchestrator, get_provenance, get_settings
from docos.model.ids import new_patch_id
from docos.model.patch import Patch, ReversiblePatch
from docos.services.provenance import accessibility, sensitive, signing

router = APIRouter(prefix="/documents", tags=["semantic"])

# Ops that act on an existing node and therefore require a valid ``target_id``.
_TARGETED_OPS = frozenset(
    {"set_text", "update_node", "retag", "redact", "unredact", "remove_node", "move_node"}
)


@router.post("/{doc_id}/patches", response_model=PatchResponse)
async def create_patch(
    doc_id: str, body: PatchRequest, session: Session = Depends(db_session)
) -> PatchResponse:
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    if body.ops:
        for op in body.ops:
            if op.op in _TARGETED_OPS and (op.target_id is None or op.target_id not in doc.nodes):
                raise HTTPException(status_code=422, detail=f"unknown target_id for op '{op.op}'")
        patch = ReversiblePatch(
            id=new_patch_id(),
            patches=[Patch(op=o.op, target_id=o.target_id, payload=o.payload) for o in body.ops],
            inverse=[],
            intent=body.instruction,
            created_at=datetime.now(UTC),
        )
    else:
        patch = await orchestrator.interpret(doc, body.instruction or "")

    applied = bool(patch.patches)
    new_version_id: str | None = None

    if applied:
        updated = orchestrator.apply(doc, patch)
        new_version_id = provenance.commit_version(updated, patch=patch)
        record = session.get(Document, doc_id)
        if record is not None:
            record.current_version_id = new_version_id

    provenance.record_event(
        doc_id,
        "patch.created",
        actor="api",
        detail={
            "patch_id": patch.id,
            "applied": applied,
            "intent": patch.intent,
            "explicit": bool(body.ops),
        },
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=applied,
        new_version_id=new_version_id,
        intent=patch.intent,
    )


@router.post("/{doc_id}/sanitize-metadata", response_model=PatchResponse)
async def sanitize_metadata(doc_id: str, session: Session = Depends(db_session)) -> PatchResponse:
    """Strip risky embedded metadata as a reversible, audited edit."""
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    patch = provenance.sanitize_metadata(doc)
    updated = orchestrator.apply(doc, patch)
    new_version_id = provenance.commit_version(updated, patch=patch)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id

    provenance.record_event(
        doc_id, "metadata.sanitized", actor="api", detail={"patch_id": patch.id}
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=True,
        new_version_id=new_version_id,
        intent=patch.intent,
    )


@router.get("/{doc_id}/sensitive", response_model=SensitiveScanResponse)
def scan_sensitive(doc_id: str, session: Session = Depends(db_session)) -> SensitiveScanResponse:
    """Detect PII/secrets in the document without changing it (preview for redaction)."""
    _record, doc = _load_latest(session, doc_id)
    findings = sensitive.scan_document(doc)
    return SensitiveScanResponse(
        doc_id=doc_id,
        findings=findings,
        summary=sensitive.summarize(findings),
        node_count=len(sensitive.redaction_node_ids(findings)),
    )


@router.post("/{doc_id}/redact-sensitive", response_model=PatchResponse)
def redact_sensitive(doc_id: str, session: Session = Depends(db_session)) -> PatchResponse:
    """One-click "clean before export": redact every detected PII/secret node.

    Builds a single reversible redaction patch over the detected nodes and runs it
    through the same apply → commit_version → audit path as any other edit, so it is
    versioned and undoable. Redaction is true removal on export (see writers/redaction).
    """
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    findings = sensitive.scan_document(doc)
    node_ids = sensitive.redaction_node_ids(findings)

    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="redact", target_id=nid) for nid in node_ids],
        inverse=[],
        intent=f"redact {len(node_ids)} sensitive item(s) before export",
        created_at=datetime.now(UTC),
    )

    applied = bool(patch.patches)
    new_version_id: str | None = None
    if applied:
        updated = orchestrator.apply(doc, patch)
        new_version_id = provenance.commit_version(updated, patch=patch)
        record = session.get(Document, doc_id)
        if record is not None:
            record.current_version_id = new_version_id

    provenance.record_event(
        doc_id,
        "sensitive.redacted",
        actor="api",
        detail={
            "patch_id": patch.id,
            "node_count": len(node_ids),
            "categories": sensitive.summarize(findings),
        },
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=applied,
        new_version_id=new_version_id,
        intent=patch.intent,
    )


@router.post("/{doc_id}/remediate-accessibility", response_model=PatchResponse)
def remediate_accessibility(doc_id: str, session: Session = Depends(db_session)) -> PatchResponse:
    """Auto-fix accessibility (heading tags, reading order, image alt) as a reversible patch."""
    record, doc = _load_latest(session, doc_id)
    orchestrator = get_orchestrator()
    provenance = get_provenance(session)

    ops = accessibility.remediation_ops(doc)
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent=f"accessibility remediation ({len(ops)} fix(es))",
        created_at=datetime.now(UTC),
    )

    applied = bool(patch.patches)
    new_version_id: str | None = None
    if applied:
        updated = orchestrator.apply(doc, patch)
        new_version_id = provenance.commit_version(updated, patch=patch)
        record = session.get(Document, doc_id)
        if record is not None:
            record.current_version_id = new_version_id

    provenance.record_event(
        doc_id,
        "accessibility.remediated",
        actor="api",
        detail={"patch_id": patch.id, "ops": len(ops)},
    )
    session.commit()

    return PatchResponse(
        doc_id=doc_id,
        patch_id=patch.id,
        applied=applied,
        new_version_id=new_version_id,
        intent=patch.intent,
    )


@router.post("/{doc_id}/sign", response_model=SignatureResponse)
def sign_document(
    doc_id: str, body: SignRequest, session: Session = Depends(db_session)
) -> SignatureResponse:
    """Apply a tamper-evident e-signature, committed as a new version."""
    record, doc = _load_latest(session, doc_id)
    secret = get_settings().signing_secret
    signed = signing.sign(doc, signer=body.signer, secret=secret)

    provenance = get_provenance(session)
    new_version_id = provenance.commit_version(signed)
    record = session.get(Document, doc_id)
    if record is not None:
        record.current_version_id = new_version_id
    provenance.record_event(doc_id, "document.signed", actor="api", detail={"signer": body.signer})
    session.commit()

    return SignatureResponse(
        doc_id=doc_id,
        signed=True,
        valid=True,
        signer=signed.signature.signer,
        signed_at=signed.signature.signed_at,
    )


@router.get("/{doc_id}/signature", response_model=SignatureResponse)
def signature_status(doc_id: str, session: Session = Depends(db_session)) -> SignatureResponse:
    """Report signature status, re-verifying the digest against current content."""
    _record, doc = _load_latest(session, doc_id)
    valid = signing.verify(doc, secret=get_settings().signing_secret)
    return SignatureResponse(
        doc_id=doc_id,
        signed=doc.signature.signed,
        valid=valid,
        signer=doc.signature.signer,
        signed_at=doc.signature.signed_at,
    )
