"""Read-only document intelligence: ask questions and summarize, with citations.

Unlike the chat-with-PDF tools (NotebookLM, ChatPDF), this runs over the **canonical
model**, so a single implementation answers across every format and every answer cites
the node ids it drew from. The retrieval + extraction core is deterministic and runs
fully offline — the privacy-first promise holds with ``LLM_PROVIDER=noop``. When a real
provider is configured, the same cited excerpts are handed to the LLM to phrase a
fluent answer, so we never lose the citation trail.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.services.docengine.writers.redaction import is_redacted
from docos.services.semantic.llm.base import LLMClient

_MAX_CITATIONS = 5
_EXCERPT_CHARS = 200
# Tiny stopword list — enough to stop function words from dominating term overlap.
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how in is it its of on or that the to "
    "was were what when where which who why will with you your".split()
)
_WORD = re.compile(r"[A-Za-z0-9']+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_NUM = re.compile(r"\d[\d,.]*")

ANSWER_SYSTEM = (
    "You answer questions about a document using ONLY the provided excerpts. Each excerpt "
    "is prefixed with its node id. Be concise and do not invent facts not in the excerpts. "
    "If the excerpts do not contain the answer, say so."
)
SUMMARY_SYSTEM = (
    "You summarize a document using ONLY the provided excerpts. Produce a concise, faithful "
    "summary in a few sentences. Do not invent facts not present in the excerpts."
)


class Citation(BaseModel):
    node_id: str
    excerpt: str


class AnswerResult(BaseModel):
    answer: str
    citations: list[Citation]
    used_llm: bool
    human_review_required: bool = False


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SummaryResult(BaseModel):
    summary: str
    citations: list[Citation]
    used_llm: bool
    human_review_required: bool = False


@lru_cache(maxsize=1)
def _stemmer():
    import snowballstemmer

    return snowballstemmer.stemmer("english")


@lru_cache(maxsize=8192)
def _norm(word: str) -> str:
    """Lowercase + Snowball (Porter2) stemming so morphological variants match.

    e.g. 'refunds'→'refund', 'renting'→'rent', 'payments'→'payment'. This is morphological
    normalisation, not synonymy: 'salary' and 'compensation' still differ (that needs embeddings).
    """
    return _stemmer().stemWord(word.lower())


def _tokens(text: str) -> set[str]:
    return {w for w in (_norm(m.group()) for m in _WORD.finditer(text)) if w not in _STOPWORDS}


def _text_nodes(doc: CanonicalDocument) -> list[tuple[str, str]]:
    """(node_id, text) for every non-redacted text-bearing node, in reading order."""
    out: list[tuple[str, str]] = []
    for node in doc.walk():
        text = (getattr(node, "text", "") or "").strip()
        if text and not is_redacted(doc, node.id):
            out.append((node.id, text))
    return out


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rstrip() + "…"


def retrieve(doc: CanonicalDocument, query: str, k: int = _MAX_CITATIONS) -> list[tuple[str, str]]:
    """Top-k (node_id, text) nodes by query-term overlap; reading order breaks ties."""
    terms = _tokens(query)
    if not terms:
        return []
    scored: list[tuple[int, int, str, str]] = []  # (-score, order, node_id, text)
    for order, (node_id, text) in enumerate(_text_nodes(doc)):
        score = len(terms & _tokens(text))
        if score:
            scored.append((-score, order, node_id, text))
    scored.sort()
    return [(node_id, text) for _, _, node_id, text in scored[:k]]


def _extractive_answer(hits: list[tuple[str, str]]) -> str:
    if not hits:
        return "I couldn't find anything about that in this document."
    return " ".join(text for _, text in hits)


def _extractive_summary(doc: CanonicalDocument) -> tuple[str, list[tuple[str, str]]]:
    nodes = _text_nodes(doc)
    if not nodes:
        return "This document has no extractable text.", []
    lead = nodes[:_MAX_CITATIONS]
    sentences = [_SENTENCE.split(text)[0] for _, text in lead]
    return " ".join(sentences), lead


def _context(hits: list[tuple[str, str]]) -> str:
    return "\n".join(f"[{node_id}] {text}" for node_id, text in hits)


def _human_review_required(text: str, citations: list[Citation], *, offline: bool) -> bool:
    """Offline/noop gate: flag answers that lack citation support."""
    if not offline:
        return False
    if not citations:
        return True
    cited = " ".join(c.excerpt for c in citations).lower()
    nums = set(_NUM.findall(text))
    return bool(nums) and not all(n in cited for n in nums)


async def answer(
    doc: CanonicalDocument, question: str, llm: LLMClient, *, use_llm: bool
) -> AnswerResult:
    """Answer ``question`` from the document's own text, citing the nodes used."""
    hits = retrieve(doc, question)
    citations = [Citation(node_id=nid, excerpt=_excerpt(text)) for nid, text in hits]

    if use_llm and hits:
        resp = await llm.complete(
            system=ANSWER_SYSTEM, user=f"Question: {question}\n\nExcerpts:\n{_context(hits)}"
        )
        if resp.text.strip():
            return AnswerResult(answer=resp.text.strip(), citations=citations, used_llm=True)

    answer = _extractive_answer(hits)
    return AnswerResult(
        answer=answer,
        citations=citations,
        used_llm=False,
        human_review_required=_human_review_required(answer, citations, offline=not use_llm),
    )


CHAT_SYSTEM = (
    "You answer questions about a document in a multi-turn conversation, using ONLY the provided "
    "excerpts (each prefixed with its node id). Use the prior turns for context (e.g. resolving "
    '"it"/"they"), but never invent facts not in the excerpts. If the excerpts do not contain the '
    "answer, say so. Be concise."
)


def _history_query(history: list[ChatTurn], question: str) -> str:
    """Bias retrieval with recent *user* turns so follow-ups ('who signed it?') keep context."""
    recent_user = [t.content for t in history if t.role == "user"][-2:]
    return " ".join([*recent_user, question]).strip()


async def chat(
    doc: CanonicalDocument,
    history: list[ChatTurn],
    question: str,
    llm: LLMClient,
    *,
    use_llm: bool,
) -> AnswerResult:
    """Answer a follow-up question with conversation history, citing the nodes used this turn.

    Retrieval runs through the semantic seam (BM25 ⊕ embeddings when configured), biased by recent
    user turns. Offline (``use_llm=False``) returns a deterministic extractive answer over this
    turn's hits — history only shapes retrieval, never fabricates. Redaction-aware throughout.
    """
    from docos.services.semantic import search  # local import: search imports reader (avoid cycle)

    hits = search.semantic_retrieve(doc, _history_query(history, question))
    citations = [Citation(node_id=nid, excerpt=_excerpt(text)) for nid, text in hits]

    if use_llm and hits:
        messages: list[dict] = [{"role": t.role, "content": t.content} for t in history]
        messages.append(
            {"role": "user", "content": f"Question: {question}\n\nExcerpts:\n{_context(hits)}"}
        )
        resp = await llm.converse(system=CHAT_SYSTEM, messages=messages)
        if resp.text.strip():
            return AnswerResult(answer=resp.text.strip(), citations=citations, used_llm=True)

    answer = _extractive_answer(hits)
    return AnswerResult(
        answer=answer,
        citations=citations,
        used_llm=False,
        human_review_required=_human_review_required(answer, citations, offline=not use_llm),
    )


TRANSLATE_SYSTEM = (
    "You are a translator. Translate the document text into the requested target language, "
    "preserving meaning and structure. Output only the translation."
)


async def translate(doc: CanonicalDocument, target_language: str, llm: LLMClient) -> str:
    """Translate the document text into ``target_language`` (requires an LLM provider)."""
    body = "\n".join(text for _, text in _text_nodes(doc))
    resp = await llm.complete(
        system=TRANSLATE_SYSTEM, user=f"Target language: {target_language}\n\nText:\n{body}"
    )
    return resp.text.strip()


async def summarize(doc: CanonicalDocument, llm: LLMClient, *, use_llm: bool) -> SummaryResult:
    """Summarize the document, citing the nodes the summary draws from."""
    extractive, lead = _extractive_summary(doc)
    citations = [Citation(node_id=nid, excerpt=_excerpt(text)) for nid, text in lead]

    if use_llm and lead:
        resp = await llm.complete(system=SUMMARY_SYSTEM, user=f"Excerpts:\n{_context(lead)}")
        if resp.text.strip():
            return SummaryResult(summary=resp.text.strip(), citations=citations, used_llm=True)

    return SummaryResult(
        summary=extractive,
        citations=citations,
        used_llm=False,
        human_review_required=_human_review_required(extractive, citations, offline=not use_llm),
    )
