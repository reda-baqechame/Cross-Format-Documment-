"""OCR & structure service: scan cleanup, recognition, tables, reading order."""

from docos.services.ocr.interface import OcrStructureService
from docos.services.ocr.tesseract import TesseractOcr

__all__ = ["OcrStructureService", "TesseractOcr"]
