"""Agent-quality eval harness (Phase E5).

Labeled end-to-end cases for the document agent. Two scoring modes share one case set:

* **Offline (structural)** — runs the deterministic ``run_agent`` and checks the *contract*: the
  right tools are selected, edits are proposed (never committed), and review/PII intents pull in the
  right tool. This runs in CI today with no provider and must be 100% green.
* **Provider (answer-quality)** — when an LLM provider is configured, runs the iterative
  ``run_agent_loop`` and additionally scores answer correctness, safe abstention, and resolvable
  citations. The gate is ≥95% of answer checks; this is what verifies the brain is production-grade
  once a key is supplied.

No "best/500×" assertions — the harness measures and reports.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[2] / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.ids import new_doc_id, new_node_id  # noqa: E402
from docos.model.nodes import ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.semantic import reader  # noqa: E402
from docos.services.semantic.agents import run_agent, run_agent_loop  # noqa: E402
from docos.services.semantic.llm.noop import LocalNoopClient  # noqa: E402
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl  # noqa: E402

# Structural gate: the deterministic contract must hold for every case (offline, in CI).
STRUCTURAL_GATE = 1.0
# Grounding gate: the deterministic Q&A answer must be faithful to its citations and abstain when
# the fact is absent (offline, in CI). 100% — a hallucinated/unsupported answer is never acceptable.
GROUNDING_GATE = 1.0
# Answer gate: with a provider configured, labeled-answer correctness must clear this bar.
ANSWER_GATE = 0.95

# A digit run (optionally with separators), used as a deterministic faithfulness probe: every number
# an answer states must trace back to a cited excerpt — the cheapest catch for invented figures.
_NUM = re.compile(r"\d[\d,.]*")


@dataclass(frozen=True)
class Case:
    name: str
    lines: tuple[str, ...]
    goal: str
    expect_tools: tuple[str, ...]
    expect_proposal: bool = False
    expect_answer_contains: tuple[str, ...] = ()
    expect_abstain: bool = False
    citation_required: bool = False


CASES: tuple[Case, ...] = (
    Case(
        name="fact_qa_invoice_number",
        lines=("Commercial Invoice", "Invoice number: INV-42", "Total due: $100.00"),
        goal="What is the invoice number?",
        expect_tools=("classify", "extract"),
        expect_answer_contains=("42",),
        citation_required=True,
    ),
    Case(
        name="abstain_when_unsupported",
        lines=("Team picnic notes", "We will meet at the park on Saturday."),
        goal="What is the contract's governing law?",
        expect_tools=("classify",),
        expect_abstain=True,
    ),
    Case(
        name="contract_risk_review",
        lines=(
            "Services Agreement",
            "This Agreement is made between Acme Corp and Beta LLC.",
            "This Agreement shall automatically renew for successive one-year terms.",
        ),
        goal="Review this contract for risks.",
        expect_tools=("pack_review",),
        expect_answer_contains=("renew",),
    ),
    Case(
        name="propose_edit_not_commit",
        lines=("Commercial Invoice", "Total due: $100.00"),
        goal="Change the total to $200.",
        expect_tools=("classify",),
        expect_proposal=True,
    ),
    Case(
        name="pii_scan",
        lines=("Memo", "Reach me at jane@example.com or 555-123-4567."),
        goal="Find and redact all PII.",
        expect_tools=("sensitive_scan",),
    ),
)


@dataclass(frozen=True)
class GroundingCase:
    name: str
    lines: tuple[str, ...]
    question: str
    must_contain: tuple[str, ...] = ()  # tokens a faithful answer should surface
    must_abstain: bool = False  # the fact is absent → the answer must decline, not invent


# Deterministic Q&A faithfulness cases (offline). These hit ``reader.answer(use_llm=False)`` — the
# exact surface users query — and prove it (a) draws stated numbers from cited text and (b) abstains
# instead of fabricating when the document doesn't contain the answer.
GROUNDING_CASES: tuple[GroundingCase, ...] = (
    GroundingCase(
        name="answer_traces_to_citation",
        lines=("Commercial Invoice", "Invoice number: INV-42", "Total due: $100.00"),
        question="What is the invoice number?",
        must_contain=("42",),
    ),
    GroundingCase(
        name="abstain_on_absent_clause",
        lines=("Team picnic notes", "We will meet at the park on Saturday."),
        question="What is the contract's governing law?",
        must_abstain=True,
    ),
    GroundingCase(
        name="no_fabricated_total",
        lines=("Meeting memo", "The all-hands is on Friday in room 3."),
        question="What is the total amount due?",
        must_abstain=True,
    ),
)


@dataclass
class ScoreCard:
    name: str
    mode: str  # "offline" | "grounding" | "provider"
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def _doc(lines: tuple[str, ...]) -> CanonicalDocument:
    now = datetime.now(UTC)
    root = RootNode(id=new_node_id("root"))
    doc = CanonicalDocument(
        doc_id=new_doc_id(),
        root_id=root.id,
        meta=DocumentMeta(
            source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
        ),
    )
    doc.add_node(root)
    for i, line in enumerate(lines):
        p = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=i)
        r = RunNode(id=new_node_id(), parent_id=p.id, text=line)
        p.children.append(r.id)
        root.children.append(p.id)
        doc.add_node(p)
        doc.add_node(r)
    return doc


def _texts(doc: CanonicalDocument) -> list[str]:
    return [getattr(n, "text", "") for n in doc.nodes.values() if n.type == "run"]


async def score_offline(case: Case) -> ScoreCard:
    """Structural contract via the deterministic agent (no provider needed)."""
    doc = _doc(case.lines)
    before = _texts(doc)
    run = await run_agent(doc, case.goal, orchestrator=SemanticOrchestratorImpl(LocalNoopClient()))
    tools = {s.tool for s in run.steps}
    checks = {
        f"tool:{t}": (t in tools) for t in case.expect_tools
    }
    if case.expect_proposal:
        checks["proposal_present"] = run.proposed_patch is not None
    # Never commits: the document the agent saw is unchanged.
    checks["no_commit"] = _texts(doc) == before
    return ScoreCard(name=case.name, mode="offline", checks=checks)


async def score_grounding(case: GroundingCase) -> ScoreCard:
    """Faithfulness of the deterministic, offline Q&A answer (no provider needed).

    Either the answer abstains (absent fact → no invented number), or it is supported: it carries
    citations and every number it states appears in a cited excerpt.
    """
    doc = _doc(case.lines)
    res = await reader.answer(doc, case.question, LocalNoopClient(), use_llm=False)
    answer = res.answer
    cited = " ".join(c.excerpt for c in res.citations).lower()
    checks: dict[str, bool] = {}

    if case.must_abstain:
        markers = ("couldn't find", "could not find", "no extractable", "not ", "n/a")
        checks["abstained"] = any(m in answer.lower() for m in markers)
        # Abstention must be honest: no fabricated figures when nothing was cited.
        checks["no_fabricated_number"] = bool(res.citations) or not _NUM.search(answer)
    else:
        checks["has_citations"] = bool(res.citations)
        for tok in case.must_contain:
            checks[f"contains:{tok}"] = tok.lower() in answer.lower()
        checks["numbers_traceable"] = all(n in cited for n in set(_NUM.findall(answer)))

    return ScoreCard(name=case.name, mode="grounding", checks=checks)


async def score_with_provider(case: Case, llm, orchestrator) -> ScoreCard:
    """Answer-quality via the iterative loop (requires a configured provider)."""
    doc = _doc(case.lines)
    before = _texts(doc)
    run = await run_agent_loop(doc, case.goal, llm=llm, orchestrator=orchestrator)
    tools = {s.tool for s in run.steps}
    answer = (run.answer or "").lower()
    checks: dict[str, bool] = {f"tool:{t}": (t in tools) for t in case.expect_tools}
    checks["no_commit"] = _texts(doc) == before
    if case.expect_proposal:
        checks["proposal_present"] = run.proposed_patch is not None
    if case.expect_answer_contains:
        checks["answer_match"] = all(s.lower() in answer for s in case.expect_answer_contains)
    if case.expect_abstain:
        abstain_markers = ("not", "no ", "couldn't", "cannot", "unable", "isn't", "n/a")
        checks["abstained"] = any(m in answer for m in abstain_markers)
    if case.citation_required:
        node_ids = {n for n in doc.nodes}
        checks["citations_resolvable"] = bool(run.citations) and all(
            c.get("node_id") in node_ids for c in run.citations
        )
    # Faithfulness: any number the model states in its answer must trace to a cited excerpt — a
    # deterministic catch for invented figures, even with a real provider.
    nums = set(_NUM.findall(answer))
    if nums:
        cited_text = " ".join(str(c.get("text", "")) for c in run.citations).lower()
        checks["faithful_numbers"] = all(n in cited_text for n in nums)
    return ScoreCard(name=case.name, mode="provider", checks=checks)


def aggregate(cards: list[ScoreCard]) -> tuple[int, int]:
    """Return (checks_passed, checks_total) across all cards."""
    passed = sum(1 for c in cards for v in c.checks.values() if v)
    total = sum(1 for c in cards for _ in c.checks.values())
    return passed, total
