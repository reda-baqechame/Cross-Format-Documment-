"""Tesseract-backed OCR & structure service.

Turns a scanned image into *positioned* text — word-level :class:`RunNode`s carrying a bounding
box and a confidence score — rather than a flat string. Low-confidence words are tagged
(``attrs["ocr_review"]``) so they're flagged for review, never silently trusted. Reading order is
inferred geometrically (top-to-bottom, then left-to-right).

Engine-agnostic and best-effort: it uses ``pytesseract.image_to_data`` when available and degrades
to ``[]`` when no Tesseract engine / language data is present, so callers can always fall back.
"""

from __future__ import annotations

import io

from docos.model.geometry import BBox
from docos.model.ids import new_node_id
from docos.model.nodes import BaseNode, RunNode, TableNode
from docos.services.ocr.interface import OcrStructureService

# Below this Tesseract confidence (0–100) a word is tagged for human review.
_REVIEW_BELOW = 60.0
# Reading-order row bucketing tolerance (px) so words on the same line group together.
_ROW_TOLERANCE = 12.0


class TesseractOcr(OcrStructureService):
    def __init__(self, languages: str = "eng") -> None:
        self.languages = languages

    def cleanup(self, image: bytes) -> bytes:
        """Grayscale + autocontrast to improve recognition; returns PNG bytes."""
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(image))
        img = ImageOps.autocontrast(ImageOps.grayscale(img))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    def recognize(self, image: bytes) -> list[RunNode]:
        """Recognise word-level text spans with bounding boxes + confidence.

        Returns ``[]`` when no Tesseract engine is available (callers fall back to flat text or to
        ingesting the image without recovered text).
        """
        try:
            import pytesseract
            from PIL import Image

            pytesseract.get_tesseract_version()  # raises if the binary is missing
        except Exception:  # noqa: BLE001 - OCR is optional; degrade to no structured output
            return []

        try:
            img = Image.open(io.BytesIO(image))
            data = pytesseract.image_to_data(
                img, lang=self.languages, output_type=pytesseract.Output.DICT
            )
        except Exception:  # noqa: BLE001 - a recognition failure is non-fatal
            return []

        runs: list[RunNode] = []
        for i, text in enumerate(data.get("text", [])):
            word = (text or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except (KeyError, ValueError, IndexError):
                conf = -1.0
            if conf < 0:  # Tesseract emits -1 for non-text regions
                continue
            x, y = float(data["left"][i]), float(data["top"][i])
            w, h = float(data["width"][i]), float(data["height"][i])
            runs.append(
                RunNode(
                    id=new_node_id(),
                    text=word,
                    bbox=BBox(x0=x, y0=y, x1=x + w, y1=y + h),
                    attrs={"confidence": round(conf, 1), "ocr_review": conf < _REVIEW_BELOW},
                )
            )
        return runs

    def extract_tables(self, image: bytes) -> list[TableNode]:
        """Grid detection from a raster image is not yet implemented (honest best-effort).

        PDF-native tables are extracted upstream by the PDF adapter; scanned-grid detection would
        need line/cell heuristics and is deferred rather than faked.
        """
        return []

    def infer_reading_order(self, nodes: list[BaseNode]) -> list[str]:
        """Top-to-bottom, then left-to-right, bucketing words onto rows by y position."""

        def key(node: BaseNode) -> tuple[float, float]:
            box = getattr(node, "bbox", None)
            if box is None:
                return (0.0, 0.0)
            return (round(box.y0 / _ROW_TOLERANCE), box.x0)

        return [n.id for n in sorted(nodes, key=key)]
