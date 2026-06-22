"""Send-Ready Check / Document X-Ray — one verdict on whether a document is safe and
complete to send.

This composes the existing detectors in a *single pass* over the canonical model, so one
report covers TXT, DOCX, PDF, XLSX, PPTX and OCR'd scans alike — exactly the cross-format
"X-ray" the per-format incumbents (Office Document Inspector, Litera Metadact) cannot give.
It folds together:

* the sensitive-data scanner (``sensitive.scan_document``) — exposed PII/secrets,
* document health (``health.compute_health``) — hidden metadata, unapplied redactions,
  accessibility, integrity seal,
* unfilled form fields — completeness.

Every failing check names a one-click ``fix_action`` that maps to an *existing* reversible
op, so the "X-ray" reveal and the "clean before you send" fix share one engine.

Pure, deterministic and fully offline — the LLM is never required.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument
from docos.services.provenance.health import compute_health
from docos.services.provenance.sensitive import CATEGORY_LABELS, scan_document, summarize

# Fix-action identifiers — shared with the (later) /clean route and the frontend so the
# one-click fixes route to the existing reversible ops.
FIX_REDACT_PII = "redact_pii"
FIX_SANITIZE_METADATA = "sanitize_metadata"
FIX_APPLY_REDACTIONS = "apply_redactions"

# Status precedence, worst-last, for rolling individual checks up into one verdict.
_RANK = {"pass": 0, "warn": 1, "fail": 2}
_VERDICT = {0: "ready", 1: "needs_fixes", 2: "blocked"}


class ReadinessCheck(BaseModel):
    """One line of the X-ray report. ``detail`` never echoes a detected secret."""

    id: str  # stable id, e.g. "exposed_pii"
    label: str
    status: str  # "pass" | "warn" | "fail"
    detail: str
    count: int = 0  # how many items this check found
    fixable: bool = False
    fix_action: str | None = None  # one of the FIX_* constants when fixable


class ReadinessReport(BaseModel):
    verdict: str  # "ready" | "needs_fixes" | "blocked"
    summary: str
    checks: list[ReadinessCheck] = Field(default_factory=list)


def _unfilled_required_fields(doc: CanonicalDocument) -> list[str]:
    """Node ids of required form fields that are still blank."""
    out: list[str] = []
    for node in doc.nodes.values():
        if node.type != "field" or not getattr(node, "required", False):
            continue
        value = getattr(node, "value", None)
        if value is None or (isinstance(value, str) and not value.strip()):
            out.append(node.id)
    return out


def _pii_phrase(counts: dict[str, int]) -> str:
    """e.g. ``2 email addresses, 1 US Social Security number`` — no raw values."""
    parts: list[str] = []
    for category, n in counts.items():
        label = CATEGORY_LABELS.get(category, category).lower()
        parts.append(f"{n} {label}" + ("s" if n != 1 and not label.endswith("s") else ""))
    return ", ".join(parts)


def build_report(doc: CanonicalDocument) -> ReadinessReport:
    """Run every check over ``doc`` and roll the results into one send-ready verdict."""
    checks: list[ReadinessCheck] = []
    health = compute_health(doc)

    # ── unapplied redactions — the only hard block (hidden text can still leak) ──────────
    if health.has_pending_redactions:
        checks.append(
            ReadinessCheck(
                id="pending_redactions",
                label="Unapplied redactions",
                status="fail",
                detail=(
                    "Redactions are marked but not yet burned in — the hidden text can "
                    "still be recovered. Apply them to produce a clean copy."
                ),
                fixable=True,
                fix_action=FIX_APPLY_REDACTIONS,
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                id="pending_redactions",
                label="Redactions",
                status="pass",
                detail="No unapplied redactions.",
            )
        )

    # ── exposed sensitive data ──────────────────────────────────────────────────────────
    findings = scan_document(doc)
    if findings:
        counts = summarize(findings)
        checks.append(
            ReadinessCheck(
                id="exposed_pii",
                label="Exposed sensitive data",
                status="warn",
                detail=(
                    f"Found {_pii_phrase(counts)} in the text that nobody has redacted. "
                    "Anyone you send this to can read it."
                ),
                count=len(findings),
                fixable=True,
                fix_action=FIX_REDACT_PII,
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                id="exposed_pii",
                label="Sensitive data",
                status="pass",
                detail="No exposed emails, card numbers, SSNs, phone numbers or IPs found.",
            )
        )

    # ── hidden metadata ─────────────────────────────────────────────────────────────────
    if health.metadata_risk:
        checks.append(
            ReadinessCheck(
                id="hidden_metadata",
                label="Hidden metadata",
                status="warn",
                detail=(
                    "Embedded metadata (author, edit history, comments) is present and "
                    "travels with the file. Strip it before sending."
                ),
                fixable=True,
                fix_action=FIX_SANITIZE_METADATA,
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                id="hidden_metadata",
                label="Hidden metadata",
                status="pass",
                detail="No risky embedded metadata, or it has already been sanitized.",
            )
        )

    # ── completeness: required fields left blank (needs user input, not auto-fixable) ───
    unfilled = _unfilled_required_fields(doc)
    has_fields = any(n.type == "field" for n in doc.nodes.values())
    if unfilled:
        checks.append(
            ReadinessCheck(
                id="unfilled_fields",
                label="Unfilled required fields",
                status="warn",
                detail=f"{len(unfilled)} required field(s) are still blank.",
                count=len(unfilled),
            )
        )
    elif has_fields:
        checks.append(
            ReadinessCheck(
                id="unfilled_fields",
                label="Form fields",
                status="pass",
                detail="All required fields are filled.",
            )
        )

    worst = max((_RANK[c.status] for c in checks), default=0)
    verdict = _VERDICT[worst]
    n_issues = sum(1 for c in checks if c.status != "pass")
    if verdict == "ready":
        summary = "Ready to send — no issues found."
    elif verdict == "needs_fixes":
        summary = f"{n_issues} issue(s) to review before sending."
    else:
        summary = "Blocked — fix the failing check before sending."

    return ReadinessReport(verdict=verdict, summary=summary, checks=checks)
