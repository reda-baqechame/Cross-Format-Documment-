"""Cloud IDP (Intelligent Document Processing) provider seam.

Default is **local** — the deterministic extractor + Tesseract already wired into the app — so this
provider is consulted only as an *enhancement* when a cloud IDP is configured, and the caller always
falls back to local results. ``TextractIdp`` uses AWS Textract via boto3 (already a dependency);
``ExternalIdp`` POSTs to a custom IDP endpoint over HTTPS. Both activate only with credentials.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

_TIMEOUT_S = 60.0


class IdpField(BaseModel):
    key: str
    value: str
    confidence: float = 0.0


class IdpProvider(ABC):
    name: str

    @abstractmethod
    def analyze(self, data: bytes, mime: str) -> list[IdpField]:
        """Return key/value fields extracted from the document bytes."""


class TextractIdp(IdpProvider):
    """AWS Textract FORMS analysis (boto3). Gated by the S3/AWS credentials in settings."""

    name = "textract"

    def __init__(self, access_key: str | None, secret_key: str | None, region: str | None) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region or "us-east-1"

    def analyze(self, data: bytes, mime: str) -> list[IdpField]:
        import boto3  # imported lazily; only used when Textract is configured

        client = boto3.client(
            "textract",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        resp = client.analyze_document(Document={"Bytes": data}, FeatureTypes=["FORMS"])
        return _parse_textract(resp)

    # split out for unit-testing the parser without AWS
    @staticmethod
    def _parse(resp: dict) -> list[IdpField]:
        return _parse_textract(resp)


def _parse_textract(resp: dict) -> list[IdpField]:
    """Turn Textract KEY_VALUE_SET blocks into IdpFields."""
    blocks = {b["Id"]: b for b in resp.get("Blocks", [])}

    def words_of(block: dict) -> str:
        out: list[str] = []
        for rel in block.get("Relationships", []) or []:
            if rel["Type"] != "CHILD":
                continue
            for cid in rel["Ids"]:
                child = blocks.get(cid, {})
                if child.get("BlockType") == "WORD":
                    out.append(child.get("Text", ""))
        return " ".join(out).strip()

    fields: list[IdpField] = []
    for block in blocks.values():
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in (block.get("EntityTypes") or []):
            continue
        key_text = words_of(block)
        value_text = ""
        for rel in block.get("Relationships", []) or []:
            if rel["Type"] == "VALUE":
                for vid in rel["Ids"]:
                    value_text = words_of(blocks.get(vid, {}))
        if key_text:
            fields.append(
                IdpField(key=key_text, value=value_text, confidence=block.get("Confidence", 0.0))
            )
    return fields


class ExternalIdp(IdpProvider):
    """A custom IDP service: POST the document bytes, get back ``{fields: [{key, value}]}``."""

    name = "external"

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def analyze(self, data: bytes, mime: str) -> list[IdpField]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = httpx.post(
            f"{self.base_url}/analyze",
            headers=headers,
            files={"document": ("document", data, mime)},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        body = resp.json()
        return [IdpField(**f) for f in body.get("fields", [])]
