"""OCR engine selection.

Resolves the configured :class:`OcrStructureService` from settings, defaulting to the always-present
Tesseract engine. When ``OCR_ENGINE=paddle`` is set and PaddleOCR is actually installed, the
stronger PaddleOCR engine is used; otherwise the choice degrades silently to Tesseract so OCR never
becomes a hard dependency. The single place the rest of the app asks "which OCR engine do I use?".
"""

from __future__ import annotations

from docos.services.ocr.interface import OcrStructureService
from docos.services.ocr.tesseract import TesseractOcr
from docos.settings import get_settings


def get_ocr_service() -> OcrStructureService:
    """Return the configured OCR engine, falling back to Tesseract when Paddle is unavailable."""
    if get_settings().ocr_engine == "paddle":
        from docos.services.ocr.paddle import PaddleOcr, paddle_available

        if paddle_available():
            return PaddleOcr()
    return TesseractOcr()
