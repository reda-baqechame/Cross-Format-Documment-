"""Object-storage abstraction. Local filesystem by default; S3/MinIO for cloud modes."""

from docos.storage.blob import BlobStore
from docos.storage.local import LocalBlobStore

__all__ = ["BlobStore", "LocalBlobStore"]
