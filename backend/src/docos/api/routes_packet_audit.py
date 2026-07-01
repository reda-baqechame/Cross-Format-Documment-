"""``/packets`` — first-class expert packet audit API.

A packet is a named group of documents audited together by one expert vertical. This is
the surface the Command Center UI calls: create a packet, add documents, run the audit,
read the cited report, apply reversible fixes, and export a clean packet.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.access import get_owned_document, owner_clause
from docos.api.routes_documents import _load_latest
from docos.api.schemas import ExpertReportResponse
from docos.api.session import Actor, get_actor
from docos.db.models import DocumentVersion, Packet, PacketAuditRun, PacketDocument
from docos.deps import blob_store_dep, db_session, get_provenance, get_registry
from docos.model.serialize import from_dict
from docos.services.expert.fixes import FixPlan, fix_for
from docos.services.expert.report_html import render_expert_report_html
from docos.services.expert.result_contract import from_expert_report
from docos.services.expert.schemas import ExpertReport
from docos.services.expert.verticals import ap as ap_vertical
from docos.services.expert.verticals import contracts as contracts_vertical
from docos.services.expert.verticals import hr as hr_vertical
from docos.services.expert.verticals import import_export as ie_vertical
from docos.services.expert.verticals import insurance as insurance_vertical
from docos.services.provenance import validation
from docos.storage.blob import BlobStore

router = APIRouter(tags=["packets"])

# Registry of available expert verticals by pack id.
_VERTICALS = {
    "import_export": ie_vertical,
    "ap": ap_vertical,
    "contracts": contracts_vertical,
    "hr": hr_vertical,
    "insurance": insurance_vertical,
}


class PacketCreate(BaseModel):
    name: str
    pack: str  # vertical id, e.g. "import_export"


class PacketOut(BaseModel):
    id: str
    name: str
    pack: str
    document_ids: list[str]
    created_at: str


class AddDocuments(BaseModel):
    document_ids: list[str]


class ApplyFixesRequest(BaseModel):
    finding_ids: list[str]


class FixPlanOut(BaseModel):
    finding_id: str
    document_id: str
    title: str
    auto_fixable: bool
    patch_count: int


def _document_id_for_finding(finding) -> str | None:
    if finding.evidence:
        return finding.evidence[0].document_id
    return None


def _plans_for_report(report: ExpertReport) -> list[FixPlan]:
    plans: list[FixPlan] = []
    for finding in report.findings:
        if not finding.fix_available:
            continue
        doc_id = _document_id_for_finding(finding)
        if not doc_id:
            continue
        plan = fix_for(finding, doc_id)
        if plan is not None:
            plans.append(plan)
    return plans


def _load_doc(session: Session, doc_id: str, actor: Actor):
    record = get_owned_document(session, doc_id, actor)
    if record.current_version_id is None:
        raise HTTPException(status_code=409, detail=f"document {doc_id} has no version")
    version = session.get(DocumentVersion, record.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="version not found")
    return record, from_dict(version.model)


def _score_bps(score: float) -> int:
    """Store the readiness score as basis points (0..10000) to avoid float-in-SQLite loss."""
    return int(round(max(0.0, min(1.0, score)) * 10000))


def _from_bps(bps: int) -> float:
    return round(bps / 10000, 4)


def _owns_packet(session: Session, packet_id: str, actor: Actor) -> Packet:
    p = session.get(Packet, packet_id)
    if p is None or not _packet_visible(p, actor):
        raise HTTPException(status_code=404, detail="packet not found")
    return p


def _packet_visible(p: Packet, actor: Actor) -> bool:
    # Same ownership rule as documents: session id for anonymous, user id when logged in.
    if actor.user_id and p.owner_user_id == actor.user_id:
        return True
    return p.owner_session_id == actor.session_id and p.owner_user_id is None


def _packet_doc_ids(session: Session, packet_id: str) -> list[str]:
    rows = session.scalars(
        select(PacketDocument).where(PacketDocument.packet_id == packet_id)
    ).all()
    return [r.document_id for r in rows]


def _to_out(session: Session, p: Packet) -> PacketOut:
    return PacketOut(
        id=p.id,
        name=p.name,
        pack=p.pack,
        document_ids=_packet_doc_ids(session, p.id),
        created_at=p.created_at.isoformat() if p.created_at else datetime.now(UTC).isoformat(),
    )


@router.post("/packets", response_model=PacketOut, status_code=201)
def create_packet(
    body: PacketCreate,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> PacketOut:
    if body.pack not in _VERTICALS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown pack '{body.pack}'. Available: {sorted(_VERTICALS)}",
        )
    p = Packet(
        id=str(uuid.uuid4()),
        name=body.name,
        pack=body.pack,
        owner_session_id=None if actor.user_id else actor.session_id,
        owner_user_id=actor.user_id,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return _to_out(session, p)


@router.get("/packets", response_model=list[PacketOut])
def list_packets(
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> list[PacketOut]:
    stmt = select(Packet).where(owner_clause(Packet.owner_session_id, Packet.owner_user_id, actor))
    packets = session.scalars(stmt).all()
    return [_to_out(session, p) for p in packets]


@router.post("/packets/{packet_id}/documents", response_model=PacketOut)
def add_documents(
    packet_id: str,
    body: AddDocuments,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> PacketOut:
    p = _owns_packet(session, packet_id, actor)
    existing = set(_packet_doc_ids(session, packet_id))
    for doc_id in body.document_ids:
        if doc_id in existing:
            continue
        # Enforce ownership of each added document (404 on cross-owner, like documents).
        get_owned_document(session, doc_id, actor)
        session.add(PacketDocument(packet_id=packet_id, document_id=doc_id))
    session.commit()
    return _to_out(session, p)


def _load_packet_docs(
    session: Session, packet_id: str, actor: Actor
) -> list[tuple[str, str | None, object]]:
    """Load every packet document's latest canonical model with ownership enforced."""
    out: list[tuple[str, str | None, object]] = []
    for doc_id in _packet_doc_ids(session, packet_id):
        record = get_owned_document(session, doc_id, actor)
        if record.current_version_id is None:
            raise HTTPException(status_code=409, detail=f"document {doc_id} has no version")
        version = session.get(DocumentVersion, record.current_version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="version not found")
        out.append((doc_id, record.title, from_dict(version.model)))
    return out


@router.post("/packets/{packet_id}/audit", response_model=ExpertReport)
def run_audit(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> ExpertReport:
    p = _owns_packet(session, packet_id, actor)
    vertical = _VERTICALS.get(p.pack)
    if vertical is None:
        raise HTTPException(status_code=400, detail=f"packet pack '{p.pack}' not available")
    docs = _load_packet_docs(session, packet_id, actor)
    if not docs:
        raise HTTPException(status_code=409, detail="packet has no documents to audit")
    report = vertical.audit(packet_id, docs)
    run = PacketAuditRun(
        id=str(uuid.uuid4()),
        packet_id=packet_id,
        pack=p.pack,
        verdict=report.verdict,
        readiness_score=_score_bps(report.readiness_score),
        report=report.model_dump(mode="json"),
    )
    session.add(run)
    session.commit()
    return report


def _latest_run(session: Session, packet_id: str) -> PacketAuditRun:
    run = session.scalars(
        select(PacketAuditRun)
        .where(PacketAuditRun.packet_id == packet_id)
        .order_by(PacketAuditRun.created_at.desc())
    ).first()
    if run is None:
        raise HTTPException(
            status_code=404, detail="no audit run yet; POST /packets/{id}/audit first"
        )
    return run


def _report_from_run(run: PacketAuditRun) -> ExpertReport:
    return ExpertReport.model_validate(run.report)


@router.get("/packets/{packet_id}/report", response_model=ExpertReportResponse)
def get_report(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> ExpertReportResponse:
    _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    result = from_expert_report(packet_id, report)
    return ExpertReportResponse(**report.model_dump(), result=result)


@router.get("/packets/{packet_id}/findings")
def get_findings(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    return {
        "verdict": report.verdict,
        "readiness_score": report.readiness_score,
        "findings": [f.model_dump(mode="json") for f in report.findings],
    }


@router.get("/packets/{packet_id}/evidence")
def get_evidence(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    """Every cited evidence ref across the latest run, deduplicated."""
    _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    seen: dict[str, dict] = {}
    for f in report.findings:
        for ev in f.evidence:
            key = "|".join(
                str(x) for x in (ev.document_id, ev.page_number, ev.node_id, ev.raw_text)
            )
            seen.setdefault(key, ev.model_dump(mode="json"))
    return {"evidence": list(seen.values())}


@router.get("/packets/{packet_id}/score")
def get_score(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    return {
        "verdict": report.verdict,
        "readiness_score": report.readiness_score,
        "blocking": sum(1 for f in report.findings if f.severity == "blocking"),
        "warning": sum(1 for f in report.findings if f.severity == "warning"),
        "info": sum(1 for f in report.findings if f.severity == "info"),
        "human_review_required": sum(1 for f in report.findings if f.human_review_required),
    }


@router.post("/packets/{packet_id}/fixes/plan")
def plan_fixes(
    packet_id: str,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    p = _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    plans = _plans_for_report(report)
    return {
        "packet_id": packet_id,
        "pack": p.pack,
        "plans": [
            FixPlanOut(
                finding_id=pl.finding_id,
                document_id=pl.document_id,
                title=pl.title,
                auto_fixable=pl.auto_fixable,
                patch_count=len(pl.patches),
            ).model_dump()
            for pl in plans
        ],
    }


@router.post("/packets/{packet_id}/fixes/apply")
def apply_fixes(
    packet_id: str,
    body: ApplyFixesRequest,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
) -> dict:
    _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    by_id = {f.id: f for f in report.findings}
    applied: list[str] = []
    for fid in body.finding_ids:
        finding = by_id.get(fid)
        if finding is None or not finding.fix_available:
            continue
        doc_id = _document_id_for_finding(finding)
        if not doc_id:
            continue
        plan = fix_for(finding, doc_id)
        if plan is None:
            continue
        _record, doc = _load_doc(session, doc_id, actor)
        for patch in plan.patches:
            apply_and_commit(
                session,
                doc_id,
                doc,
                patch,
                actor=actor,
                event="packet.fix_applied",
                detail={"packet_id": packet_id, "finding_id": fid, "plan_title": plan.title},
            )
            _record, doc = _load_doc(session, doc_id, actor)
        applied.append(fid)
    return {"packet_id": packet_id, "applied_finding_ids": applied}


@router.get("/packets/{packet_id}/report/download")
def download_report(
    packet_id: str,
    format: str = Query("html"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
):
    p = _owns_packet(session, packet_id, actor)
    report = _report_from_run(_latest_run(session, packet_id))
    if format != "html":
        raise HTTPException(status_code=400, detail="only format=html is supported")
    html = render_expert_report_html(title=p.name, packet_id=packet_id, report=report)
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="packet-{packet_id}-report.html"'},
    )


@router.get("/packets/{packet_id}/export")
async def export_packet(
    packet_id: str,
    format: str = Query("zip"),
    actor: Actor = Depends(get_actor),
    session: Session = Depends(db_session),
    blob_store: BlobStore = Depends(blob_store_dep),
) -> Response:
    """Export all packet documents. ``zip`` (default) or a single ``pdf`` when one PDF doc."""
    from docos.api.routes_export import _render_export, _safe_filename, _signature_valid

    p = _owns_packet(session, packet_id, actor)
    doc_ids = _packet_doc_ids(session, packet_id)
    if not doc_ids:
        raise HTTPException(status_code=409, detail="packet has no documents")

    if format == "pdf":
        if len(doc_ids) != 1:
            raise HTTPException(status_code=400, detail="pdf export requires exactly one document")
        record, doc = _load_latest(session, doc_ids[0], actor)
        if record.source_format != "pdf":
            raise HTTPException(status_code=400, detail="pdf export requires a PDF source document")
        registry = get_registry()
        data, mime, ext = await _render_export(doc, record, "pdf", registry, blob_store)
        report = validation.validate_export(doc, "pdf", data, signature_valid=_signature_valid(doc))
        filename = f"{_safe_filename(p.name, packet_id)}.{ext}"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-DocOS-Validation": validation.status(report),
            "X-DocOS-Validation-Summary": report.summary,
        }
        return Response(content=data, media_type=mime, headers=headers)

    if format != "zip":
        raise HTTPException(status_code=400, detail="format must be zip or pdf")

    registry = get_registry()
    buf = io.BytesIO()
    validations: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_id in doc_ids:
            record, doc = _load_latest(session, doc_id, actor)
            fmt = record.source_format if record.source_format in {"pdf", "docx", "txt"} else "txt"
            if fmt not in {"pdf", "docx", "txt"}:
                fmt = "txt"
            try:
                data, _mime, ext = await _render_export(doc, record, fmt, registry, blob_store)
            except HTTPException:
                data, _mime, ext = await _render_export(doc, record, "txt", registry, blob_store)
            vreport = validation.validate_export(
                doc, fmt, data, signature_valid=_signature_valid(doc)
            )
            validations.append(validation.status(vreport))
            name = f"{_safe_filename(record.title, doc_id)}.{ext}"
            zf.writestr(name, data)
    summary = "pass" if all(v == "pass" for v in validations) else "warn"
    headers = {
        "Content-Disposition": f'attachment; filename="{_safe_filename(p.name, packet_id)}.zip"',
        "X-DocOS-Validation": summary,
        "X-DocOS-Validation-Summary": f"{len(validations)} document(s) exported",
    }
    get_provenance(session).record_event(
        packet_id,
        "packet.exported",
        actor=actor.user_id or actor.session_id,
        detail={"format": "zip", "document_count": len(doc_ids)},
    )
    session.commit()
    return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)
