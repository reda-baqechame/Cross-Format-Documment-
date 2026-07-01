"""Optional LLM judge — turns deterministic findings into business prose.

The judge NEVER introduces new findings. Its only jobs are: (1) rewrite the executive
summary in clearer business language, and (2) flag any low-confidence finding as
``human_review_required``. Offline (no provider) it is a pure no-op and the report keeps
its deterministic summary — there is no "fake AI" path.

This is the disciplined way to use an LLM in an expert system: the model writes the
narrative, the rules write the facts. The facts always win.
"""

from __future__ import annotations

import json

from docos.services.expert.schemas import ExpertReport

_SYSTEM = (
    "You are an expert document auditor. You are given a JSON report produced by "
    "DETERMINISTIC rules. You may ONLY: (a) rewrite 'executive_summary' in clearer business "
    "prose, preserving every number and verdict exactly; (b) for any finding whose "
    "confidence < 0.7, set 'human_review_required' true. You MUST NOT add, remove, merge, "
    "or reclassify findings, change any verdict, severity, evidence, or value, or invent "
    "any fact not present in the input. Return ONLY the same JSON schema with those two "
    "permitted edits. If you cannot comply, return the input unchanged."
)


async def refine_summary(report: ExpertReport, llm) -> ExpertReport:
    """If an LLM client is provided, rewrite the prose; else return the report unchanged."""
    if llm is None:
        return report
    try:
        payload = report.model_dump_json()
        resp = await llm.complete(_SYSTEM, payload)
        data = json.loads(resp.text)
        # Only accept the two permitted fields; ignore anything else the model returned.
        if isinstance(data, dict) and isinstance(data.get("executive_summary"), str):
            report = report.model_copy(update={"executive_summary": data["executive_summary"]})
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            by_id = {f["id"]: f for f in data["findings"] if isinstance(f, dict) and "id" in f}
            new_findings = []
            for f in report.findings:
                override = by_id.get(f.id)
                if override and isinstance(override.get("human_review_required"), bool):
                    f = f.model_copy(
                        update={"human_review_required": override["human_review_required"]}
                    )
                new_findings.append(f)
            report = report.model_copy(update={"findings": new_findings})
    except Exception:
        # Never let a provider hiccup corrupt a deterministic report.
        return report
    return report
