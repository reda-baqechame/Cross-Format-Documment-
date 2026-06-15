"""S3 blob store round-trips through an injected fake client (no AWS / moto)."""

from __future__ import annotations

import asyncio
import io

from docos.storage.s3 import S3BlobStore


class FakeS3Client:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body):  # noqa: N803 - boto3 kwarg names
        self.store[(Bucket, Key)] = Body
        return {}

    def get_object(self, *, Bucket, Key):  # noqa: N803
        return {"Body": io.BytesIO(self.store[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803
        self.store.pop((Bucket, Key), None)
        return {}

    def generate_presigned_url(self, op, *, Params, ExpiresIn):  # noqa: N803
        return f"https://s3.test/{Params['Bucket']}/{Params['Key']}"


def test_s3_put_get_delete_roundtrip():
    fake = FakeS3Client()
    store = S3BlobStore(bucket="docos", client=fake)

    async def scenario():
        key = await store.put("uploads/a", b"hello s3")
        assert key == "uploads/a"
        assert await store.get("uploads/a") == b"hello s3"
        url = await store.url("uploads/a")
        assert url == "https://s3.test/docos/uploads/a"
        await store.delete("uploads/a")
        assert ("docos", "uploads/a") not in fake.store

    asyncio.run(scenario())
