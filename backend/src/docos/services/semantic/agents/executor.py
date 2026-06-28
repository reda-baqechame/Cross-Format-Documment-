"""Iterative agentic executor — the production-grade tool-calling brain.

Where ``agent.py`` runs a fixed deterministic sequence (always-on, offline), this drives a *real*
plan → call tool → observe → repeat loop using a hosted model's native tool use. The model decides
which tools to run, reads their structured observations, and iterates until it can answer — citing
the exact nodes it used. Mutations are only ever *proposed* (a reversible-patch preview); the loop
never commits, mirroring the apply→commit→audit discipline of the rest of the system.

Safety rails (hard):
* Bounded steps and tool calls — the loop cannot run away.
* Read tools execute deterministically; ``propose_edit`` returns a preview, never a commit.
* Every step is recorded in the transcript the UI renders and the user approves.
* Offline (``LLM_PROVIDER=noop``) never reaches here — the route falls back to ``run_agent``.
"""

from __future__ import annotations

from docos.model.document import CanonicalDocument
from docos.services.semantic import classify, search
from docos.services.semantic import preview as preview_service
from docos.services.semantic.agents import tools as toolbox
from docos.services.semantic.agents.agent import AgentRun, AgentStep, _recommended
from docos.services.semantic.interface import SemanticOrchestrator
from docos.services.semantic.llm.base import LLMClient

_MAX_STEPS = 6
_MAX_CITATIONS = 6

SYSTEM_PROMPT = (
    "You are DocOS, a meticulous, business-grade document agent. You operate over a canonical "
    "document model through tools. Your job: accomplish the user's goal precisely and prove it.\n\n"
    "Operating rules:\n"
    "1. Ground every claim in the document. Call read tools (classify, extract, intelligence, "
    "sensitive_scan, pack_review, search) before asserting facts. Never invent values.\n"
    "2. Cite. When you state a fact drawn from the document, reference the node id(s) you got it "
    "from (use the `search` tool to locate and cite exact passages).\n"
    "3. To change the document, call `propose_edit` with a clear natural-language instruction. "
    "It returns a preview only; the user applies edits after review, never you. Never claim "
    "you changed the document.\n"
    "4. Abstain honestly. If the document doesn't support the goal, say so plainly rather than "
    "guessing.\n"
    "5. Be efficient: stop calling tools and give your final answer as soon as you can support it. "
    "Keep the answer concise and decision-ready."
)


def _read_tool_schemas() -> list[dict]:
    """LLM tool schemas for the deterministic read tools + search + propose_edit."""
    schemas: list[dict] = []
    for name, tool in toolbox.read_tools().items():
        schemas.append(
            {
                "name": name,
                "description": tool.description,
                "input_schema": {"type": "object", "properties": {}, "required": []},
            }
        )
    schemas.append(
        {
            "name": "search",
            "description": (
                "Find and cite the most relevant passages for a query; returns node ids + text."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    )
    schemas.append(
        {
            "name": "propose_edit",
            "description": (
                "Propose a reversible edit to the document from a natural-language instruction. "
                "Returns a preview; the change is NOT committed (the user approves it)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"instruction": {"type": "string"}},
                "required": ["instruction"],
            },
        }
    )
    return schemas


def _intro(doc: CanonicalDocument, goal: str) -> str:
    c = classify.classify(doc)
    return (
        f"Document type (heuristic): {c.label} (confidence {c.confidence:.2f}).\n"
        f"Goal: {goal}\n\n"
        "Use tools to accomplish and verify the goal, then give a final cited answer."
    )


async def run_agent_loop(
    doc: CanonicalDocument,
    goal: str,
    *,
    llm: LLMClient,
    orchestrator: SemanticOrchestrator,
    max_steps: int = _MAX_STEPS,
    allow_destructive: bool = False,
) -> AgentRun:
    """Run the bounded plan→act→observe loop and return a transcript with a cited answer.

    Mutations are proposed (preview) only — never committed. ``allow_destructive`` is reserved for
    future destructive tools (e.g. redaction) and currently only annotates the transcript.
    """
    schemas = _read_tool_schemas()
    messages: list[dict] = [{"role": "user", "content": _intro(doc, goal)}]
    steps: list[AgentStep] = []
    citations: list[dict] = []
    proposed = None
    warnings: list[str] = []
    answer = ""

    for _ in range(max_steps):
        resp = await llm.converse(SYSTEM_PROMPT, messages, tools=schemas)
        if not resp.tool_calls:
            answer = resp.text.strip()
            break

        messages.append(
            {"role": "assistant", "content": resp.text, "tool_calls": resp.tool_calls}
        )
        results: list[dict] = []
        for call in resp.tool_calls:
            name = call.get("name", "")
            args = call.get("input", {}) or {}
            cid = call.get("id", name)

            if name == "search":
                hits = search.semantic_retrieve(doc, str(args.get("query", goal)), k=_MAX_CITATIONS)
                for node_id, text in hits:
                    if not any(c["node_id"] == node_id for c in citations):
                        citations.append({"node_id": node_id, "text": text})
                summary = (
                    "; ".join(f"[{nid}] {txt[:80]}" for nid, txt in hits) or "no matching passages"
                )
                steps.append(
                    AgentStep(
                        tool="search", kind="read", label="Search & cite",
                        status="done", summary=f"{len(hits)} passage(s) found",
                        data={"hits": [{"node_id": n, "text": t} for n, t in hits]},
                    )
                )
                results.append({"id": cid, "name": name, "content": summary})

            elif name == "propose_edit":
                instruction = str(args.get("instruction", goal))
                patch = await orchestrator.interpret(doc, instruction)
                proposed = preview_service.build_preview(doc, patch.patches)
                steps.append(
                    AgentStep(
                        tool="modify", kind="mutate", label="Propose edits",
                        status="proposed" if patch.patches else "skipped",
                        summary=(
                            f"Proposed {proposed.change_count} reversible change(s) — preview "
                            "shown, approval required before commit."
                        ),
                        requires_approval=True,
                    )
                )
                results.append(
                    {
                        "id": cid, "name": name,
                        "content": (
                            f"Proposed {proposed.change_count} change(s); preview returned, "
                            "awaiting user approval (not committed)."
                        ),
                    }
                )

            else:
                tool = toolbox.get_tool(name)
                if tool is not None and tool.run is not None:
                    r = tool.run(doc)
                    steps.append(
                        AgentStep(
                            tool=name, kind="read", label=tool.label,
                            status="done", summary=r.summary, data=r.data,
                        )
                    )
                    results.append({"id": cid, "name": name, "content": r.summary})
                else:
                    results.append(
                        {"id": cid, "name": name, "content": f"unknown tool '{name}'"}
                    )

        messages.append({"role": "tool", "tool_results": results})
    else:
        warnings.append(f"Agent reached the {max_steps}-step limit before finishing.")
        if not answer:
            answer = "I ran out of steps before fully resolving the goal; see the steps above."

    return AgentRun(
        goal=goal,
        classification=classify.classify(doc).label,
        used_llm=True,
        steps=steps,
        proposed_patch=proposed,
        recommended_actions=_recommended(doc),
        warnings=warnings,
        answer=answer,
        citations=citations,
    )
