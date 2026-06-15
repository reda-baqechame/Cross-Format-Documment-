"""S3 / MinIO blob store — used in enterprise and cloud privacy modes.

STUB: wiring is sketched against boto3 but methods raise ``NotImplementedError``
until the cloud deployment path is built out. ``LocalBlobStore`` is the default.
"""

from __future__ import annotations

from docos.storage.blob import BlobStore


class S3BlobStore(BlobStore):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        # Extension point: lazily build a boto3 client here.

    async def put(self, key: str, data: bytes) -> str:
        raise NotImplementedError("S3BlobStore.put — implement for cloud/enterprise mode")

    async def get(self, key: str) -> bytes:
        raise NotImplementedError("S3BlobStore.get — implement for cloud/enterprise mode")

    async def url(self, key: str) -> str:
        raise NotImplementedError("S3BlobStore.url — return a presigned URL")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("S3BlobStore.delete — implement for cloud/enterprise mode")
