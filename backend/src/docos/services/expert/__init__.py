"""Expert DocumentOps spine — the one core all vertical packs plug into.

A business packet is not a pile of files; it is one transaction whose facts must agree.
This package turns deterministic per-document extraction into evidence-bound findings,
a normalized business fact graph, and an expert report that proves every claim it makes.

Design rules (enforced everywhere):
  * Deterministic first, LLM second. Rules extract/compare; the judge only writes prose.
  * Evidence-bound only. Every factual finding cites document_id + page + node_id + raw_text.
    No evidence → human_review_required = True. Never hallucinate.
  * Reversible + auditable. Fixes are ReversiblePatch plans, never raw file rewrites.
  * Honest. Nothing is "expert_verified" until it passes a golden corpus.
"""

from docos.services.expert.schemas import (
    DocumentSummary,
    EvidenceRef,
    ExpertFinding,
    ExpertReport,
    ExtractedField,
    FindingSeverity,
    FindingType,
    MissingDocument,
    RecommendedAction,
    Verdict,
)

__all__ = [
    "DocumentSummary",
    "EvidenceRef",
    "ExpertFinding",
    "ExpertReport",
    "ExtractedField",
    "FindingSeverity",
    "FindingType",
    "MissingDocument",
    "RecommendedAction",
    "Verdict",
]
