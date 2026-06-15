"""OCR & structure service interface.

Scanned documents need more than character recognition: the report stresses that
OCR output requires review and that reading order must be inferred. This interface
keeps those as explicit, reviewable steps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from docos.model.nodes import BaseNode, RunNode, TableNode


class OcrStructureService(ABC):
    @abstractmethod
    def cleanup(self, image: bytes) -> bytes:
        """Deskew/denoise/binarize before recognition."""

    @abstractmethod
    def recognize(self, image: bytes) -> list[RunNode]:
        """Recognize text spans with bounding boxes and confidence."""

    @abstractmethod
    def extract_tables(self, image: bytes) -> list[TableNode]:
        """Detect and extract tabular structure."""

    @abstractmethod
    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        """Return node ids in inferred reading order."""
