"""Multi-engine OCR consensus — run several engines and keep the most confident recognition.

Single-engine OCR is at the mercy of one model's weaknesses. The consensus engine runs every
available engine over the page and returns the result set with the highest mean word confidence
("best-engine routing") — a deterministic, explainable consensus. With only Tesseract installed it
is exactly Tesseract (graceful degradation); add PaddleOCR and the stronger result wins per page.
Structure (tables, reading order, cleanup) follows the primary engine.
"""

from __future__ import annotations

from docos.model.nodes import BaseNode, RunNode, TableNode
from docos.services.ocr.interface import OcrStructureService


def _mean_confidence(runs: list[RunNode]) -> float:
    confs = [float(r.attrs.get("confidence", 0.0)) for r in runs]
    return sum(confs) / len(confs) if confs else 0.0


class ConsensusOcr(OcrStructureService):
    """Compose several OCR engines; ``recognize`` returns the highest-mean-confidence result."""

    def __init__(self, engines: list[OcrStructureService]) -> None:
        if not engines:
            raise ValueError("ConsensusOcr requires at least one engine")
        self.engines = engines

    @property
    def _primary(self) -> OcrStructureService:
        return self.engines[0]

    def cleanup(self, image: bytes) -> bytes:
        return self._primary.cleanup(image)

    def extract_tables(self, image: bytes) -> list[TableNode]:
        return self._primary.extract_tables(image)

    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        return self._primary.infer_reading_order(nodes)

    def recognize(self, image: bytes) -> list[RunNode]:
        best: list[RunNode] = []
        best_score = -1.0
        for engine in self.engines:
            runs = engine.recognize(image)
            if not runs:
                continue
            score = _mean_confidence(runs)
            if score > best_score:
                best, best_score = runs, score
        return best
