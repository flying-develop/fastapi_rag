"""Async S3-compatible object storage client (MinIO for local dev).

Uses `aioboto3` — an async-native wrapper around `boto3`/`aiobotocore` —
so object storage calls fit the project's "all I/O through async/await"
requirement the same way `asyncpg`/SQLAlchemy async do for Postgres.
"""

import logging

import aioboto3
from botocore.exceptions import ClientError

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

_session = aioboto3.Session()

# `head_bucket`'s error code for "bucket doesn't exist" varies between AWS
# S3 and S3-compatible implementations (MinIO included) depending on
# permissions/version — check both rather than relying on one.
_BUCKET_NOT_FOUND_ERROR_CODES = {"404", "NoSuchBucket"}


def _client():
    """Return an async-context-manager S3 client configured from `Settings`.

    A fresh client is opened per call rather than kept open for the
    process lifetime — matches `aioboto3`'s recommended usage (the
    underlying `aiohttp` session is meant to be short-lived) and avoids
    holding a client across `Settings` changes (e.g. between tests).
    """
    settings = get_settings()
    return _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


async def ensure_bucket_exists() -> None:
    """Create the configured bucket if it doesn't exist yet.

    Idempotent — safe to call on every application startup, the same way
    `app/main.py`'s `_check_db_connection()` runs on every startup.
    """
    settings = get_settings()
    async with _client() as s3:
        try:
            await s3.head_bucket(Bucket=settings.s3_bucket)
            logger.debug(
                "s3 bucket already exists", extra={"bucket": settings.s3_bucket}
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code not in _BUCKET_NOT_FOUND_ERROR_CODES:
                raise
            await s3.create_bucket(Bucket=settings.s3_bucket)
            logger.info("s3 bucket created", extra={"bucket": settings.s3_bucket})


async def upload_file(key: str, data: bytes, content_type: str) -> None:
    """Upload `data` to the configured bucket under `key`."""
    settings = get_settings()
    async with _client() as s3:
        try:
            await s3.put_object(
                Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
            )
        except Exception as exc:
            logger.error(
                "s3 upload failed", extra={"key": key, "error_type": type(exc).__name__}
            )
            raise
    logger.info("s3 upload succeeded", extra={"key": key, "size_bytes": len(data)})


async def download_file(key: str) -> bytes:
    """Download and return the full contents of the object at `key`.

    Raises whatever `aioboto3` raises for a missing key (`ClientError`
    with a `NoSuchKey` code) — the caller (the `files` module's service
    layer) is responsible for translating that into a domain-level
    "file not found" the same way it handles a missing DB row.
    """
    settings = get_settings()
    async with _client() as s3:
        try:
            response = await s3.get_object(Bucket=settings.s3_bucket, Key=key)
            body = await response["Body"].read()
        except Exception as exc:
            logger.error(
                "s3 download failed", extra={"key": key, "error_type": type(exc).__name__}
            )
            raise
    logger.info("s3 download succeeded", extra={"key": key, "size_bytes": len(body)})
    return body
