"""DocumentOps Autopilot routes, proof report, finding review, and batch clean/audit."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.routes_export import _safe_filename
from docos.api.routes_readiness import clean_document
from docos.api.schemas import CleanResponse
from docos.api.session import Actor, get_actor
from docos.deps import blob_store_dep, db_session, get_registry
from docos.services.docengine.registry import AdapterRegistry
from docos.services.expert import autopilot as document_autopilot
from docos.services.expert.autopilot import AutopilotRunRequest, AutopilotRunResponse
from docos.services.expert.fixes import fix_for
from docos.services.expert.readiness_bridge import readiness_to_expert_findings
from docos.services.expert.result_contract import from_readiness
from docos.services.provenance import readiness
from docos.services.provenance.readiness_html import render_readiness_html
from docos.storage.blob import BlobStore

router = APIRouter(prefix="/documents", tags=["document-ops"])

_CORRECTIONS = Path(__file__).resolve().parents[4] / "evals" / "corrections"


class AutopilotApplyRequest(BaseModel):
    finding_ids: list[str] = Field(default_factory=list)


class FindingReviewRequest(BaseModel):
    accepted: bool
    note: str | None = None


class BatchDocRequest(BaseModel):
    doc_ids: list[str] = Field(min_length=1, max_length=50)


class BatchCleanResult(BaseModel):
    doc_id: str
    verdict: str
    score: int
    applied: bool = False


class BatchCleanResponse(BaseModel):
    results: list[BatchCleanResult]


class BatchAuditResponse(BaseModel):
    results: list[AutopilotRunResponse]


@router.post("/{doc_id}/autopilot/run", response_model=AutopilotRunResponse)
def autopilot_run(
    doc_id: str,
    body: AutopilotRunRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> AutopilotRunResponse:
    _record, doc = _load_latest(session, doc_id, actor)
    against = None
    if body.goal == "compare":
        if not body.against_doc_id:
            raise HTTPException(status_code=400, detail="against_doc_id required for compare goal")
        _, against = _load_latest(session, body.against_doc_id, actor)
    return document_autopilot.run(doc_id, doc, goal=body.goal, against=against)


@router.post("/{doc_id}/autopilot/apply", response_model=CleanResponse)
async def autopilot_apply(
    doc_id: str,
    body: AutopilotApplyRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> CleanResponse:
    """Apply fix plans for selected findings, then re-run clean."""
    _record, doc = _load_latest(session, doc_id, actor)
    report = readiness.build_report(doc)
    findings = readiness_to_expert_findings(doc_id, doc, report)
    target = (
        {f.id for f in findings if f.id in body.finding_ids}
        if body.finding_ids
        else {f.id for f in findings if f.fix_available}
    )
    for f in findings:
        if f.id not in target:
            continue
        plan = fix_for(f, doc_id)
        if not plan:
            continue
        for rp in plan.patches:
            apply_and_commit(
                session,
                doc_id,
                doc,
                rp,
                actor=actor,
                event="autopilot.fix_applied",
                detail={"finding_id": f.id},
            )
            _, doc = _load_latest(session, doc_id, actor)
    return await clean_document(
        doc_id, session, actor, registry=registry, blob_store=blob_store, _rate=_rate
    )


@router.get("/{doc_id}/proof-report")
def proof_report(
    doc_id: str,
    format: Literal["html", "json"] = Query("html"),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
) -> Response:
    """Unified proof artifact — same content as readiness report with expert findings."""
    record, doc = _load_latest(session, doc_id, actor)
    report = readiness.build_report(doc)
    findings = readiness_to_expert_findings(doc_id, doc, report)
    title = record.title or doc_id
    filename = _safe_filename(title, doc_id)
    if format == "json":
        payload = {
            "doc_id": doc_id,
            "result": from_readiness(doc_id, report, findings).model_dump(mode="json"),
        }
        return Response(
            content=json.dumps(payload),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}-proof-report.json"'},
        )
    html = render_readiness_html(
        title=title, doc_id=doc_id, report=report, expert_findings=findings
    )
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}-proof-report.html"'},
    )


@router.patch("/{doc_id}/findings/{finding_id}/review")
def review_finding(
    doc_id: str,
    finding_id: str,
    body: FindingReviewRequest,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    """Capture human accept/reject on a finding for the golden correction loop."""
    _load_latest(session, doc_id, actor)
    _CORRECTIONS.mkdir(parents=True, exist_ok=True)
    entry = {
        "finding_id": finding_id,
        "doc_id": doc_id,
        "accepted": body.accepted,
        "note": body.note,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "reviewer": actor.user_id or actor.session_id,
    }
    path = _CORRECTIONS / f"{finding_id}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return {"stored": str(path.relative_to(_CORRECTIONS.parent)), "entry": entry}


batch_router = APIRouter(prefix="/jobs", tags=["batch-ops"])


@batch_router.post("/batch-clean", response_model=BatchCleanResponse)
async def batch_clean(
    body: BatchDocRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    registry: AdapterRegistry = Depends(get_registry),
    blob_store: BlobStore = Depends(blob_store_dep),
    _rate: None = Depends(enforce_op_rate),
) -> BatchCleanResponse:
    results: list[BatchCleanResult] = []
    for doc_id in body.doc_ids:
        _record, doc = _load_latest(session, doc_id, actor)
        report = readiness.build_report(doc)
        findings = readiness_to_expert_findings(doc_id, doc, report)
        result = from_readiness(doc_id, report, findings)
        applied = False
        if result.fix_plans_available and result.verdict != "blocked":
            try:
                await clean_document(
                    doc_id, session, actor, registry=registry, blob_store=blob_store, _rate=_rate
                )
                applied = True
                _, doc = _load_latest(session, doc_id, actor)
                report = readiness.build_report(doc)
                findings = readiness_to_expert_findings(doc_id, doc, report)
                result = from_readiness(doc_id, report, findings)
            except Exception:
                applied = False
        results.append(
            BatchCleanResult(
                doc_id=doc_id,
                verdict=result.verdict,
                score=result.score,
                applied=applied,
            )
        )
    return BatchCleanResponse(results=results)


@batch_router.post("/batch-audit", response_model=BatchAuditResponse)
def batch_audit(
    body: BatchDocRequest,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    _rate: None = Depends(enforce_op_rate),
) -> BatchAuditResponse:
    results: list[AutopilotRunResponse] = []
    for doc_id in body.doc_ids:
        _record, doc = _load_latest(session, doc_id, actor)
        results.append(document_autopilot.run(doc_id, doc, goal="review"))
    return BatchAuditResponse(results=results)
