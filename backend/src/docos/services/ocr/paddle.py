"""PaddleOCR-backed OCR & structure service (Apache-2.0).

A stronger, multilingual alternative to the bundled Tesseract engine. Like Tesseract it returns
*positioned* word/line :class:`RunNode`s carrying a bounding box and a confidence score, and tags
low-confidence spans (``attrs["ocr_review"]``) so they are flagged for review rather than silently
trusted. Reading order is inferred geometrically, identical to the Tesseract path.

Engine-agnostic and best-effort: PaddleOCR (``paddleocr`` / ``paddlepaddle``) is an *optional*
dependency (``pip install "paddleocr>=2.7" "paddlepaddle>=2.6"``). When it is not installed — or
fails on a given image —
:meth:`recognize` returns ``[]`` so the image adapter falls back to Tesseract and then to plain
ingestion. Nothing here is required for the platform to run offline.

PaddleOCR confidence is a 0–1 probability; it is scaled to the 0–100 range used across the OCR
layer so the same ``_REVIEW_BELOW`` threshold and downstream tooling apply unchanged.
"""

from __future__ import annotations

from docos.model.geometry import BBox
from docos.model.ids import new_node_id
from docos.model.nodes import BaseNode, RunNode, TableNode
from docos.services.ocr.interface import OcrStructureService
from docos.services.ocr.tesseract import _REVIEW_BELOW, _ROW_TOLERANCE


def paddle_available() -> bool:
    """True when PaddleOCR (and its PaddlePaddle backend) can be imported."""
    try:
        import paddleocr  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency; absence is the common case
        return False
    return True


def _quad_to_bbox(quad: list[list[float]]) -> BBox:
    """Turn PaddleOCR's 4-point polygon into an axis-aligned bounding box."""
    xs = [float(p[0]) for p in quad]
    ys = [float(p[1]) for p in quad]
    return BBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys))


def _map_results(results: list) -> list[RunNode]:
    """Map a PaddleOCR ``ocr()`` result (one page) into confidence-tagged :class:`RunNode`s."""
    runs: list[RunNode] = []
    # PaddleOCR returns ``[[ [quad, (text, conf)], ... ]]`` (outer list = pages); take the page.
    page = results[0] if results and isinstance(results[0], list) else results
    for line in page or []:
        try:
            quad, (text, conf) = line[0], line[1]
        except (TypeError, ValueError, IndexError):
            continue
        text = (text or "").strip()
        if not text:
            continue
        conf100 = round(float(conf) * 100.0, 1)
        runs.append(
            RunNode(
                id=new_node_id(),
                text=text,
                bbox=_quad_to_bbox(quad),
                attrs={"confidence": conf100, "ocr_review": conf100 < _REVIEW_BELOW},
            )
        )
    return runs


class PaddleOcr(OcrStructureService):
    """PaddleOCR PP-OCR recognition behind the shared :class:`OcrStructureService` interface."""

    def __init__(self, lang: str = "en") -> None:
        self.lang = lang
        self._engine = None  # lazily constructed; model load is expensive

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR  # lazy: only when actually recognising

            self._engine = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
        return self._engine

    def cleanup(self, image: bytes) -> bytes:
        """PaddleOCR does its own preprocessing; pass the bytes through unchanged."""
        return image

    def recognize(self, image: bytes) -> list[RunNode]:
        """Recognise text spans with boxes + confidence; ``[]`` when PaddleOCR is unavailable."""
        if not paddle_available():
            return []
        try:
            results = self._get_engine().ocr(image, cls=True)
        except Exception:  # noqa: BLE001 - recognition is best-effort; caller falls back
            return []
        return _map_results(results or [])

    def extract_tables(self, image: bytes) -> list[TableNode]:
        """Table extraction is provided by the heavier PP-StructureV3 pipeline.

        Left as an honest no-op here (returns ``[]``) so the image adapter falls back to the
        conservative scanned-grid detector; wiring PP-Structure is tracked in the roadmap.
        """
        return []

    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        """Top-to-bottom, then left-to-right — identical geometry to the Tesseract path."""

        def key(node: BaseNode) -> tuple[float, float]:
            box = getattr(node, "bbox", None)
            if box is None:
                return (0.0, 0.0)
            return (round(box.y0 / _ROW_TOLERANCE), box.x0)

        return [n.id for n in sorted(nodes, key=key)]
