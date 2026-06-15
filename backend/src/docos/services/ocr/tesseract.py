"""Tesseract-backed OCR — STUB.

Extension point: ``cleanup`` with Pillow/OpenCV; ``recognize`` via
``pytesseract.image_to_data`` (text + bbox + confidence → RunNodes); table detection
via line/grid heuristics; reading order via XY-cut or column clustering. Low-confidence
spans should be tagged for human review, never silently trusted.
"""

from __future__ import annotations

from docos.model.nodes import BaseNode, RunNode, TableNode
from docos.services.ocr.interface import OcrStructureService


class TesseractOcr(OcrStructureService):
    def __init__(self, languages: str = "eng") -> None:
        self.languages = languages

    def cleanup(self, image: bytes) -> bytes:
        raise NotImplementedError("TesseractOcr.cleanup — deskew/denoise with Pillow/OpenCV")

    def recognize(self, image: bytes) -> list[RunNode]:
        raise NotImplementedError("TesseractOcr.recognize — pytesseract.image_to_data → RunNodes")

    def extract_tables(self, image: bytes) -> list[TableNode]:
        raise NotImplementedError("TesseractOcr.extract_tables")

    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        raise NotImplementedError("TesseractOcr.infer_reading_order — XY-cut / column clustering")
