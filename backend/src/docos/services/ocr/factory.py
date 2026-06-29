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


def _paddle_or_none() -> OcrStructureService | None:
    from docos.services.ocr.paddle import PaddleOcr, paddle_available

    return PaddleOcr() if paddle_available() else None


def get_ocr_service() -> OcrStructureService:
    """Return the configured OCR engine.

    ``paddle`` uses PaddleOCR when installed; ``consensus`` runs every available engine and keeps
    the most confident result. Both degrade silently to the always-present Tesseract, so OCR is
    never a hard dependency.
    """
    engine = get_settings().ocr_engine
    if engine == "paddle":
        paddle = _paddle_or_none()
        if paddle is not None:
            return paddle
    elif engine == "consensus":
        from docos.services.ocr.consensus import ConsensusOcr

        engines = [TesseractOcr()]
        paddle = _paddle_or_none()
        if paddle is not None:
            engines.append(paddle)
        return ConsensusOcr(engines)
    return TesseractOcr()
