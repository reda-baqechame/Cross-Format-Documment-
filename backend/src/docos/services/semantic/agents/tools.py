"""Agent tool registry — exposes existing document services as a typed toolbox for the AI brain.

This is additive: each tool is a thin wrapper over a service that already exists and is already
tested. The agent (``agent.py``) plans which tools to run; read tools execute deterministically and
return a structured observation, while mutate/action tools are *described* here and carried out
through the existing reversible-patch / workflow routes (so nothing bypasses the apply→commit→audit
discipline). Read tools work fully offline (no LLM), so the agent is useful even with
``LLM_PROVIDER=noop``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from docos.model.document import CanonicalDocument
from docos.services.provenance import sensitive
from docos.services.semantic import classify, extract
from docos.services.semantic.skills import autopilot

ToolKind = Literal["read", "mutate", "action"]


@dataclass(frozen=True)
class ToolResult:
    summary: str
    data: dict


@dataclass(frozen=True)
class AgentTool:
    name: str
    kind: ToolKind
    label: str
    description: str
    requires_approval: bool = False
    destructive: bool = False
    # Read tools carry a deterministic runner; mutate/action tools are executed via existing routes.
    run: Callable[[CanonicalDocument], ToolResult] | None = field(default=None)


# ── read-tool runners (deterministic, offline) ──────────────────────────────────────────────


def _run_classify(doc: CanonicalDocument) -> ToolResult:
    c = classify.classify(doc)
    return ToolResult(
        summary=f"Document classified as '{c.label}' (confidence {c.confidence:.2f}).",
        data={"label": c.label, "confidence": c.confidence, "signals": list(c.signals)},
    )


def _run_extract(doc: CanonicalDocument) -> ToolResult:
    ex = extract.extract(doc)
    return ToolResult(
        summary=f"Extracted {len(ex.entities)} entities and {len(ex.fields)} label/value fields.",
        data={
            "entities": [e.model_dump() for e in ex.entities],
            "fields": [f.model_dump() for f in ex.fields],
        },
    )


def _run_intelligence(doc: CanonicalDocument) -> ToolResult:
    report = autopilot.analyze(doc)
    findings = getattr(report, "findings", []) or []
    return ToolResult(
        summary=(
            f"Typed read: {getattr(report, 'type', 'document')} — "
            f"{len(getattr(report, 'fields', []) or [])} fields, {len(findings)} checks."
        ),
        data=report.model_dump() if hasattr(report, "model_dump") else {},
    )


def _run_sensitive(doc: CanonicalDocument) -> ToolResult:
    findings = sensitive.scan_document(doc)
    kinds: dict[str, int] = {}
    for f in findings:
        kinds[f.category] = kinds.get(f.category, 0) + 1
    return ToolResult(
        summary=f"Found {len(findings)} sensitive item(s) across {len(kinds)} kind(s).",
        data={"count": len(findings), "by_kind": kinds},
    )


# ── the registry ────────────────────────────────────────────────────────────────────────────

_TOOLS: dict[str, AgentTool] = {
    "classify": AgentTool(
        "classify", "read", "Classify document",
        "Detect the document type/workflow.", run=_run_classify,
    ),
    "extract": AgentTool(
        "extract", "read", "Extract key fields",
        "Pull entities (dates, money, contacts) and label/value fields with provenance.",
        run=_run_extract,
    ),
    "intelligence": AgentTool(
        "intelligence", "read", "Typed analysis",
        "Run the typed analyzer for the detected document kind (fields + validation checks).",
        run=_run_intelligence,
    ),
    "sensitive_scan": AgentTool(
        "sensitive_scan", "read", "Scan for sensitive data",
        "Detect PII/secrets without modifying the document.", run=_run_sensitive,
    ),
    # Mutate tools — executed via the reversible-patch route (preview→approve→commit); the agent
    # only proposes them. Described here so the brain/UI know they exist and are approval-gated.
    "modify": AgentTool(
        "modify", "mutate", "Edit document",
        "Propose reversible edits (set_text/update_node/retag/set_table_cell). Preview required.",
        requires_approval=True,
    ),
    "redact_pii": AgentTool(
        "redact_pii", "mutate", "Redact sensitive data",
        "Truly remove detected PII on export. Destructive — preview + approval required.",
        requires_approval=True, destructive=True,
    ),
    "sanitize_metadata": AgentTool(
        "sanitize_metadata", "mutate", "Strip risky metadata",
        "Remove hidden/embedded metadata before sharing. Preview required.",
        requires_approval=True,
    ),
    # Action tools — side effects via existing routes; always approval-gated.
    "export": AgentTool(
        "export", "action", "Export / convert",
        "Produce a validated output file in the requested format.",
    ),
    "route_approval": AgentTool(
        "route_approval", "action", "Route for approval/signature",
        "Send the document into an approval/signature workflow.", requires_approval=True,
    ),
}


def get_tool(name: str) -> AgentTool | None:
    return _TOOLS.get(name)


def read_tools() -> dict[str, AgentTool]:
    return {n: t for n, t in _TOOLS.items() if t.kind == "read"}


def all_tools() -> list[AgentTool]:
    return list(_TOOLS.values())
