"""Ingestion & safety gateway: validate, scan, stage uploads before parsing."""

from docos.services.ingestion.gateway import IngestionGatewayImpl
from docos.services.ingestion.interface import IngestionGateway, IngestResult, ScanResult

__all__ = ["IngestResult", "IngestionGateway", "IngestionGatewayImpl", "ScanResult"]
