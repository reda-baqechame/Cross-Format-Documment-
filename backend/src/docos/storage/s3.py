"""S3 / MinIO blob store — used in enterprise and cloud privacy modes.

Wraps a boto3 S3 client. boto3 is synchronous, so each call is dispatched to a
worker thread to honour the async ``BlobStore`` contract. The client is built lazily
(and can be injected for tests), so importing this module never requires AWS config.
"""

from __future__ import annotations

import asyncio
from typing import Any

from docos.storage.blob import BlobStore


class S3BlobStore(BlobStore):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
        return self._client

    async def put(self, key: str, data: bytes) -> str:
        await asyncio.to_thread(
            self._get_client().put_object, Bucket=self.bucket, Key=key, Body=data
        )
        return key

    async def get(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self._get_client().get_object, Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    async def url(self, key: str) -> str:
        return await asyncio.to_thread(
            self._get_client().generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=3600,
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._get_client().delete_object, Bucket=self.bucket, Key=key)
