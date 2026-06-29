"""Multi-document agentic executor — the plan→act→observe brain across a whole corpus.

Where ``executor.run_agent_loop`` reasons over one document, this reasons over *many* (e.g. "compare
these three contracts", "which invoice is the duplicate?"). It is **read/analysis only**: the tools
search and survey the corpus and every cited fact carries its source ``doc_id`` — cross-document
mutation isn't well-defined, so the loop never proposes edits.

Safety rails mirror the single-doc loop: bounded steps, deterministic tools, every step recorded,
and offline (``LLM_PROVIDER=noop``) never reaches the loop — the route falls back to the
deterministic ``run_corpus_agent`` (extractive cross-document answer).
"""

from __future__ import annotations

from docos.services.semantic import corpus as corpus_service
from docos.services.semantic.agents.agent import AgentRun, AgentStep
from docos.services.semantic.corpus import CorpusDoc
from docos.services.semantic.llm.base import LLMClient, merge_usage

_MAX_STEPS = 6
_MAX_CITATIONS = 8

SYSTEM_PROMPT = (
    "You are DocOS, a meticulous analyst working across a SET of documents. Accomplish the user's "
    "goal precisely and prove it.\n\n"
    "Operating rules:\n"
    "1. Ground every claim in the corpus. Use `search` to find relevant passages before asserting "
    "facts; never invent values.\n"
    "2. Cite. Every fact must reference the document + node it came from (search returns both).\n"
    "3. Use `list_documents` to see what's in the corpus when the goal spans/compares documents.\n"
    "4. Abstain honestly. If the corpus doesn't support the goal, say so plainly.\n"
    "5. Be efficient: stop calling tools and give a concise, decision-ready answer as soon as you "
    "can support it."
)


def _tool_schemas() -> list[dict]:
    return [
        {
            "name": "search",
            "description": (
                "Find and cite the most relevant passages for a query across ALL documents; "
                "returns document title/id + node id + text."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "list_documents",
            "description": "List the documents in the corpus (id + title) — the analysis scope.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]


def _intro(corpus: list[CorpusDoc], goal: str) -> str:
    titles = ", ".join((c.title or c.doc_id) for c in corpus[:10])
    more = "" if len(corpus) <= 10 else f" (+{len(corpus) - 10} more)"
    return (
        f"Corpus: {len(corpus)} document(s): {titles}{more}.\n"
        f"Goal: {goal}\n\n"
        "Use tools to accomplish and verify the goal, then give a final cited answer."
    )


def _do_search(
    corpus: list[CorpusDoc], query: str, citations: list[dict]
) -> tuple[AgentStep, str]:
    hits = corpus_service._retrieve_across(corpus, query, _MAX_CITATIONS)
    for c, node_id, text, _score in hits:
        if not any(x["node_id"] == node_id and x["doc_id"] == c.doc_id for x in citations):
            citations.append({"doc_id": c.doc_id, "node_id": node_id, "text": text})
    summary = (
        "; ".join(f"[{(c.title or c.doc_id)} · {nid}] {txt[:60]}" for c, nid, txt, _ in hits)
        or "no matching passages"
    )
    step = AgentStep(
        tool="search",
        kind="read",
        label="Search corpus & cite",
        status="done",
        summary=f"{len(hits)} passage(s) across {len({c.doc_id for c, *_ in hits})} doc(s)",
        data={
            "hits": [
                {"doc_id": c.doc_id, "title": c.title, "node_id": nid, "text": txt}
                for c, nid, txt, _ in hits
            ]
        },
    )
    return step, summary


def _list_documents(corpus: list[CorpusDoc]) -> tuple[AgentStep, str]:
    listing = "; ".join(f"{c.doc_id}: {c.title or '(untitled)'}" for c in corpus)
    step = AgentStep(
        tool="list_documents",
        kind="read",
        label="List documents",
        status="done",
        summary=f"{len(corpus)} document(s) in scope",
        data={"documents": [{"doc_id": c.doc_id, "title": c.title} for c in corpus]},
    )
    return step, (listing or "corpus is empty")


async def run_corpus_agent_loop(
    corpus: list[CorpusDoc],
    goal: str,
    *,
    llm: LLMClient,
    max_steps: int = _MAX_STEPS,
) -> AgentRun:
    """Bounded plan→act→observe loop over the corpus; returns a transcript with a cited answer."""
    schemas = _tool_schemas()
    messages: list[dict] = [{"role": "user", "content": _intro(corpus, goal)}]
    steps: list[AgentStep] = []
    citations: list[dict] = []
    warnings: list[str] = []
    answer = ""
    usage: dict | None = None

    for _ in range(max_steps):
        resp = await llm.converse(SYSTEM_PROMPT, messages, tools=schemas)
        usage = merge_usage(usage, resp.usage)
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
                step, summary = _do_search(corpus, str(args.get("query", goal)), citations)
            elif name == "list_documents":
                step, summary = _list_documents(corpus)
            else:
                results.append({"id": cid, "name": name, "content": f"unknown tool '{name}'"})
                continue
            steps.append(step)
            results.append({"id": cid, "name": name, "content": summary})
        messages.append({"role": "tool", "tool_results": results})
    else:
        warnings.append(f"Agent reached the {max_steps}-step limit before finishing.")
        if not answer:
            answer = "I ran out of steps before fully resolving the goal; see the steps above."

    return AgentRun(
        goal=goal,
        classification=f"corpus:{len(corpus)} documents",
        used_llm=True,
        steps=steps,
        proposed_patch=None,
        recommended_actions=[],
        warnings=warnings,
        answer=answer,
        citations=citations,
        usage=usage,
    )


async def run_corpus_agent(corpus: list[CorpusDoc], goal: str, llm: LLMClient) -> AgentRun:
    """Deterministic offline cross-document analysis: one search + an extractive answer."""
    citations: list[dict] = []
    step, _ = _do_search(corpus, goal, citations)
    nb = await corpus_service.notebook_answer(corpus, goal, llm, use_llm=False)
    return AgentRun(
        goal=goal,
        classification=f"corpus:{len(corpus)} documents",
        used_llm=False,
        steps=[step],
        proposed_patch=None,
        recommended_actions=[],
        warnings=[],
        answer=nb.answer,
        citations=citations,
    )
