"""Tests for the async S3 client — hits the real MinIO instance from
docker-compose (no mocks, per project convention). Run via:

    docker compose up -d minio
    docker compose run --rm app uv run pytest
"""

import uuid

import pytest
from botocore.exceptions import ClientError

from app.infrastructure.s3 import download_file, ensure_bucket_exists, upload_file


async def test_ensure_bucket_exists_is_idempotent() -> None:
    """Calling it twice (bucket already exists the second time) must not
    raise — this runs on every application startup."""
    await ensure_bucket_exists()
    await ensure_bucket_exists()


async def test_upload_then_download_roundtrips_bytes() -> None:
    await ensure_bucket_exists()
    key = f"test-{uuid.uuid4()}.txt"

    await upload_file(key, b"hello minio", "text/plain")
    data = await download_file(key)

    assert data == b"hello minio"


async def test_download_missing_key_raises_client_error() -> None:
    await ensure_bucket_exists()

    with pytest.raises(ClientError):
        await download_file(f"missing-{uuid.uuid4()}.txt")
