"""DocumentOps run — orchestrate classify → pack-compare → synthesize, end to end.

This is the outcome layer the planner/agent stopped short of: instead of *proposing* steps, a run
executes the read+generate pipeline in one call and returns a result a user can act on — findings,
a generated deliverable (via the report endpoint), and the next gated actions. It is read-only and
**never commits**: any mutation/route/send is surfaced as an approval-gated action, mirroring the
recipe engine. Deterministic and offline; an LLM is not required.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services import synthesis
from docos.services.packs.contracts import check_contracts
from docos.services.packs.finance import check_ap
from docos.services.packs.hr import check_onboarding
from docos.services.packs.import_export import check_packet
from docos.services.packs.insurance import check_insurance
from docos.services.semantic import classify as classify_service

# pack → (cross-document check, report-synthesis adapter). Mirrors routes_packs so the run and the
# downloadable report stay consistent.
_PACKS = {
    "import-export": (check_packet, synthesis.packet_exception_report),
    "finance": (check_ap, synthesis.ap_reconciliation_report),
    "contracts": (check_contracts, synthesis.contract_risk_report),
    "hr": (check_onboarding, synthesis.hr_onboarding_report),
    "insurance": (check_insurance, synthesis.insurance_review_report),
}

# Coarse classification-label → pack inference (best-effort; explicit `pack` always wins).
_LABEL_TO_PACK = {
    "invoice": "finance",
    "purchase_order": "finance",
    "receipt": "finance",
    "commercial_invoice": "import-export",
    "packing_list": "import-export",
    "bill_of_lading": "import-export",
    "certificate_of_origin": "import-export",
    "contract": "contracts",
    "agreement": "contracts",
    "offer_letter": "hr",
    "resume": "hr",
    "insurance_policy": "insurance",
    "insurance_claim": "insurance",
}

REPORT_FORMATS = ["pdf", "xlsx", "docx", "html", "md"]


class RunStep(BaseModel):
    tool: str
    kind: str  # read | generate | action
    status: str  # done | proposed
    summary: str
    requires_approval: bool = False


class RunFinding(BaseModel):
    severity: str
    code: str
    message: str


class GatedAction(BaseModel):
    kind: str  # route_approval | export | external_send
    label: str
    reason: str


class RunResult(BaseModel):
    run_id: str
    pack: str
    document_count: int
    classifications: dict[str, str] = Field(default_factory=dict)
    findings: list[RunFinding] = Field(default_factory=list)
    summary: str = ""
    steps: list[RunStep] = Field(default_factory=list)
    report_formats: list[str] = Field(default_factory=list)
    report_endpoint: str = ""
    gated_actions: list[GatedAction] = Field(default_factory=list)
    used_llm: bool = False


def infer_pack(labels: list[str]) -> str | None:
    """Best-effort pack from document classifications; ``None`` if nothing maps."""
    votes: dict[str, int] = {}
    for label in labels:
        pack = _LABEL_TO_PACK.get(label)
        if pack:
            votes[pack] = votes.get(pack, 0) + 1
    if not votes:
        return None
    return max(votes, key=lambda p: votes[p])


def run_documentops(
    run_id: str,
    corpus: list[tuple[str, str | None, CanonicalDocument]],
    *,
    pack: str | None = None,
) -> RunResult:
    """Execute the read+generate pipeline over a corpus and return an actionable result.

    ``corpus`` is ``(doc_id, title, doc)`` tuples (owner-scoped by the caller). ``pack`` may be
    omitted to infer it from the documents' classifications.
    """
    classifications = {did: classify_service.classify(doc).label for did, _title, doc in corpus}

    chosen = pack or infer_pack(list(classifications.values()))
    if chosen not in _PACKS:
        raise ValueError(
            f"could not determine a pack for these documents; pass one of {sorted(_PACKS)}"
        )

    check_fn, report_fn = _PACKS[chosen]
    report = check_fn(corpus)
    findings = [
        RunFinding(severity=f.severity, code=f.code, message=f.message) for f in report.findings
    ]

    steps = [
        RunStep(
            tool="classify",
            kind="read",
            status="done",
            summary=f"Classified {len(corpus)} document(s).",
        ),
        RunStep(tool=f"pack:{chosen}", kind="read", status="done", summary=report.summary),
        RunStep(
            tool="synthesize",
            kind="generate",
            status="done",
            summary=f"Generated a {chosen} report (downloadable as {', '.join(REPORT_FORMATS)}).",
        ),
    ]

    # Next steps are *proposed*, never executed here — committing/sending stays gated.
    has_errors = any(f.severity == "error" for f in findings)
    gated = [
        GatedAction(
            kind="route_approval",
            label="Route for approval",
            reason=(
                "Blocking issues found — send the report for sign-off before proceeding."
                if has_errors
                else "Optionally route the report to an approver."
            ),
        ),
        GatedAction(
            kind="export",
            label="Export / deliver the report",
            reason="Download the generated report or push it to a connected destination.",
        ),
    ]

    return RunResult(
        run_id=run_id,
        pack=chosen,
        document_count=len(corpus),
        classifications=classifications,
        findings=findings,
        summary=report.summary,
        steps=steps,
        report_formats=REPORT_FORMATS,
        report_endpoint=f"/packs/{chosen}/report",
        gated_actions=gated,
        used_llm=False,
    )
