"""Tests for `POST /files` / `GET /files/{id}` — real Postgres + MinIO
from docker-compose (see `tests/modules/dialog/test_dialog_router.py`
for why `httpx.AsyncClient` + `ASGITransport` rather than `TestClient`)."""

import httpx
import pytest

from app.infrastructure.s3 import ensure_bucket_exists
from app.main import app
from app.modules.files.api.router import get_file_service
from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.services.file_service import FileService


@pytest.fixture(autouse=True)
async def _bucket() -> None:
    await ensure_bucket_exists()


@pytest.fixture
async def client(db_session):
    def _override() -> FileService:
        return FileService(file_repository=FileRepository(db_session))

    # Same reasoning as the dialog router tests: bypass get_db entirely so
    # the request reuses the test's own db_session/transaction.
    app.dependency_overrides[get_file_service] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.pop(get_file_service, None)


async def test_upload_then_download_roundtrips_file(client) -> None:
    upload_response = await client.post(
        "/files",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )

    assert upload_response.status_code == 201
    body = upload_response.json()
    assert body["filename"] == "notes.txt"
    assert body["content_type"] == "text/plain"
    assert body["size_bytes"] == len(b"hello world")

    download_response = await client.get(f"/files/{body['id']}")

    assert download_response.status_code == 200
    assert download_response.content == b"hello world"
    # Starlette appends `; charset=utf-8` to text/* media types by default.
    assert download_response.headers["content-type"].startswith("text/plain")
    assert 'filename="notes.txt"' in download_response.headers["content-disposition"]


async def test_download_returns_404_for_missing_file(client) -> None:
    response = await client.get("/files/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "File 999999 not found"


async def test_get_metadata_returns_parse_result(client) -> None:
    upload_response = await client.post(
        "/files",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    file_id = upload_response.json()["id"]

    response = await client.get(f"/files/{file_id}/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == file_id
    assert body["parse_status"] == "skipped"
    assert body["extracted_text"] is None


async def test_get_metadata_returns_404_for_missing_file(client) -> None:
    response = await client.get("/files/999999/metadata")

    assert response.status_code == 404
    assert response.json()["detail"] == "File 999999 not found"
