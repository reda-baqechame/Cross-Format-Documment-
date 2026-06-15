"""Document-health model + computation — the product's signature panel.

Aggregates accessibility, redaction, metadata, signature, and permission state into
one DTO so the UI can show, in a single place, everything that today is scattered
across separate editors, viewers, admin consoles, and signing tools.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from docos.model.document import CanonicalDocument


class HealthFinding(BaseModel):
    level: str  # ok | info | warn | fail
    code: str
    message: str


class DocumentHealth(BaseModel):
    accessibility_score: float = 0.0
    metadata_risk: bool = False
    has_pending_redactions: bool = False
    signed: bool = False
    ready_for_signing: bool = False
    findings: list[HealthFinding] = Field(default_factory=list)


# Embedded-metadata keys that commonly leak sensitive info if not sanitized.
RISKY_META_KEYS = ("last_modified_by", "author", "comments", "revision")


def compute_health(doc: CanonicalDocument) -> DocumentHealth:
    findings: list[HealthFinding] = []

    # ── accessibility ─────────────────────────────────────────────────────────
    image_ids = [n.id for n in doc.nodes.values() if n.type == "image"]
    missing_alt = [
        n.id for n in doc.nodes.values() if n.type == "image" and not getattr(n, "alt_text", None)
    ]
    doc.accessibility.images_missing_alt = missing_alt

    checks = [
        doc.accessibility.has_doc_title,
        doc.accessibility.tagged or any(n.tags for n in doc.nodes.values()),
        len(missing_alt) == 0,
        doc.accessibility.reading_order_ok
        or all(n.reading_order is not None for n in doc.children_of(doc.root_id)),
    ]
    score = sum(1 for c in checks if c) / len(checks)
    doc.accessibility.score = round(score, 2)

    if not doc.accessibility.has_doc_title:
        findings.append(HealthFinding(level="warn", code="a11y.no_title", message="Document has no title."))
    if missing_alt:
        findings.append(
            HealthFinding(
                level="warn",
                code="a11y.missing_alt",
                message=f"{len(missing_alt)} of {len(image_ids)} images lack alt text.",
            )
        )

    # ── metadata risk ─────────────────────────────────────────────────────────
    metadata_risk = (not doc.redaction.metadata_sanitized) and any(
        doc.meta.custom.get(k) for k in RISKY_META_KEYS
    )
    if metadata_risk:
        findings.append(
            HealthFinding(
                level="warn",
                code="trust.metadata",
                message="Embedded metadata present and not yet sanitized.",
            )
        )

    # ── redaction ─────────────────────────────────────────────────────────────
    pending = bool(doc.redaction.pending)
    if pending:
        findings.append(
            HealthFinding(
                level="fail",
                code="trust.redaction_pending",
                message="Pending redactions are not yet applied — content may still leak.",
            )
        )

    if not findings:
        findings.append(HealthFinding(level="ok", code="ok", message="No issues detected."))

    return DocumentHealth(
        accessibility_score=doc.accessibility.score,
        metadata_risk=metadata_risk,
        has_pending_redactions=pending,
        signed=doc.signature.signed,
        ready_for_signing=doc.signature.ready_for_signing,
        findings=findings,
    )
