"""Tests for `FileService` — real MinIO + Postgres from docker-compose,
no mocks (per project convention, per this plan's testing setting)."""

import pytest

from app.infrastructure.s3 import ensure_bucket_exists
from app.modules.files.exceptions import StoredFileNotFoundError
from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.services.file_service import FileService


@pytest.fixture(autouse=True)
async def _bucket() -> None:
    await ensure_bucket_exists()


async def test_upload_file_stores_bytes_and_metadata(db_session) -> None:
    service = FileService(FileRepository(db_session))

    file = await service.upload_file(
        filename="notes.txt", content_type="text/plain", data=b"hello world"
    )

    assert file.id is not None
    assert file.filename == "notes.txt"
    assert file.content_type == "text/plain"
    assert file.size_bytes == len(b"hello world")
    # storage_key is generated, not the client-supplied filename, but
    # keeps the original extension.
    assert file.storage_key.endswith(".txt")
    assert file.storage_key != "notes.txt"


async def test_download_file_returns_metadata_and_original_bytes(db_session) -> None:
    service = FileService(FileRepository(db_session))
    uploaded = await service.upload_file(
        filename="data.bin", content_type="application/octet-stream", data=b"\x00\x01\x02"
    )

    file, data = await service.download_file(uploaded.id)

    assert file.id == uploaded.id
    assert data == b"\x00\x01\x02"


async def test_download_file_raises_for_missing_id(db_session) -> None:
    service = FileService(FileRepository(db_session))

    with pytest.raises(StoredFileNotFoundError):
        await service.download_file(999_999)
