"""Tests for `FileRepository` — real PostgreSQL from docker-compose,
no mocks (see `tests/conftest.py`)."""

from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.schemas.file import FileCreate


async def test_create_persists_file(db_session) -> None:
    repo = FileRepository(db_session)

    file = await repo.create(
        FileCreate(
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=1234,
            storage_key="abc123.pdf",
        )
    )

    assert file.id is not None
    assert file.filename == "report.pdf"
    assert file.content_type == "application/pdf"
    assert file.size_bytes == 1234
    assert file.storage_key == "abc123.pdf"
    assert file.created_at is not None


async def test_get_by_id_returns_none_when_missing(db_session) -> None:
    repo = FileRepository(db_session)

    assert await repo.get_by_id(999_999) is None


async def test_get_by_id_returns_created_file(db_session) -> None:
    repo = FileRepository(db_session)
    created = await repo.create(
        FileCreate(
            filename="image.png",
            content_type="image/png",
            size_bytes=42,
            storage_key="xyz789.png",
        )
    )

    found = await repo.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.storage_key == "xyz789.png"
