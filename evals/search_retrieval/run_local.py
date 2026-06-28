"""Local retrieval benchmark (deterministic, no model calls, no network).

Measures the *current* cross-document search (`semantic_search`, BM25) against a labeled query set,
split into two honest buckets:

  * **lexical** — the query shares words with the target. BM25 should nail these; this bucket is a
    CI gate (regressions fail the build).
  * **semantic** — the query shares only *meaning* (synonyms/paraphrase). BM25 cannot follow these;
    this bucket is **measured and reported, not gated** — it is the quantified ceiling that an
    embedding model (Phase D) must lift. This turns the previous anecdotal "salary != compensation"
    claim into a number.

Run from the repo root:  ``python evals/search_retrieval/run_local.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from datetime import UTC, datetime  # noqa: E402

from docos.model.document import CanonicalDocument, DocumentMeta  # noqa: E402
from docos.model.ids import new_doc_id, new_node_id  # noqa: E402
from docos.model.nodes import ParagraphNode, RootNode, RunNode  # noqa: E402
from docos.services.semantic.corpus import CorpusDoc, semantic_search  # noqa: E402
from search_retrieval.metrics import LabeledQuery, aggregate  # noqa: E402

K = 5
LEXICAL_RECALL_FLOOR = 0.90  # BM25 must keep finding word-overlap targets.


def _doc_from_text(text: str) -> CanonicalDocument:
    root = RootNode(id=new_node_id("root"))
    now = datetime.now(UTC)
    meta = DocumentMeta(
        source_format="txt", source_mime="text/plain", created_at=now, modified_at=now
    )
    doc = CanonicalDocument(doc_id=new_doc_id(), root_id=root.id, meta=meta)
    doc.add_node(root)
    para = ParagraphNode(id=new_node_id(), parent_id=root.id, reading_order=0)
    run = RunNode(id=new_node_id(), parent_id=para.id, text=text)
    para.children.append(run.id)
    root.children.append(para.id)
    doc.add_node(para)
    doc.add_node(run)
    return doc


# Labeled corpus: id -> document text. Ids are stable so queries can reference them.
CORPUS_TEXT: dict[str, str] = {
    "lease": "Residential lease agreement. The tenant shall pay rent on the first of each month.",
    "nda": "Mutual non-disclosure agreement protecting confidential information between parties.",
    "offer": "Employment offer letter stating the annual salary and the start date for the role.",
    "invoice": "Invoice for consulting services rendered, with the total amount due in 30 days.",
    "policy": "Company travel policy describing reimbursement for flights, hotels, and meals.",
    "termination": "Notice of termination ending the employment relationship, effective now.",
    "privacy": "Privacy policy explaining how personal data is collected, stored, and processed.",
    "warranty": "Limited warranty covering defects in materials and workmanship for one year.",
}


def _corpus() -> list[CorpusDoc]:
    return [
        CorpusDoc(doc_id=cid, title=cid.title(), doc=_doc_from_text(text))
        for cid, text in CORPUS_TEXT.items()
    ]


# Each query labels its relevant doc id(s). "lexical" share words; "semantic" share only meaning.
QUERIES: list[LabeledQuery] = [
    # --- lexical: word overlap with the target (BM25 should rank it #1) ---
    LabeledQuery("rent payment tenant", frozenset({"lease"}), "lexical"),
    LabeledQuery("confidential information parties", frozenset({"nda"}), "lexical"),
    LabeledQuery("annual salary start date", frozenset({"offer"}), "lexical"),
    LabeledQuery("amount due consulting", frozenset({"invoice"}), "lexical"),
    LabeledQuery("reimbursement flights hotels", frozenset({"policy"}), "lexical"),
    LabeledQuery("personal data collected stored", frozenset({"privacy"}), "lexical"),
    LabeledQuery("defects materials workmanship", frozenset({"warranty"}), "lexical"),
    # --- semantic: synonyms / paraphrase only (the lexical gap to be measured) ---
    LabeledQuery("compensation package", frozenset({"offer"}), "semantic"),
    LabeledQuery("firing an employee", frozenset({"termination"}), "semantic"),
    LabeledQuery("secrecy contract", frozenset({"nda"}), "semantic"),
    LabeledQuery("renting an apartment", frozenset({"lease"}), "semantic"),
    LabeledQuery("how you handle my information", frozenset({"privacy"}), "semantic"),
]


def _run(bucket: str, corpus: list[CorpusDoc]) -> dict[str, float]:
    results = []
    for q in (x for x in QUERIES if x.kind == bucket):
        ranked = [h.doc_id for h in semantic_search(corpus, q.query, limit=K)]
        results.append((q, ranked))
    return aggregate(results, k=K)


def main() -> int:
    corpus = _corpus()
    lexical = _run("lexical", corpus)
    semantic = _run("semantic", corpus)

    report = {
        "engine": "bm25 (lexical)",
        "k": K,
        "lexical": lexical,
        "semantic_gap": semantic,
        "lexical_recall_floor": LEXICAL_RECALL_FLOOR,
    }
    print(json.dumps(report, indent=2))

    print(
        f"\nBM25 recall@{K}: lexical={lexical['recall_at_k']:.0%}  "
        f"semantic={semantic['recall_at_k']:.0%}  (semantic = the gap embeddings must close)"
    )

    if lexical["recall_at_k"] < LEXICAL_RECALL_FLOOR:
        print(
            f"\nFAIL: lexical recall@{K} {lexical['recall_at_k']:.2f} "
            f"< floor {LEXICAL_RECALL_FLOOR}"
        )
        return 1
    print(f"\nPASS: lexical recall@{K} ≥ {LEXICAL_RECALL_FLOOR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
