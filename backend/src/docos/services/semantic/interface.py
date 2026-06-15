"""Semantic orchestrator interface.

The orchestrator is the safety boundary around AI: it translates a natural-language
instruction into a *reversible patch* it can preview, apply, and revert against the
node graph. It never regenerates a whole document.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from docos.model.document import CanonicalDocument
from docos.model.patch import ReversiblePatch


class SemanticOrchestrator(ABC):
    @abstractmethod
    async def interpret(self, doc: CanonicalDocument, instruction: str) -> ReversiblePatch:
        """Plan a reversible patch that satisfies ``instruction`` over ``doc``."""

    @abstractmethod
    def apply(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        """Apply the forward ops, returning the new document."""

    @abstractmethod
    def revert(self, doc: CanonicalDocument, patch: ReversiblePatch) -> CanonicalDocument:
        """Apply the inverse ops, returning the prior document."""
