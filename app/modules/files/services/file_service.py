"""Use cases orchestrating `File` metadata with S3-compatible storage."""

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from app.infrastructure.s3 import download_file as s3_download_file
from app.infrastructure.s3 import upload_file as s3_upload_file
from app.modules.files.exceptions import StoredFileNotFoundError
from app.modules.files.models.file import File
from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.schemas.file import FileCreate
from app.modules.files.services.file_parser import parse_to_text

logger = logging.getLogger(__name__)


def _generate_storage_key(filename: str) -> str:
    """Generate a storage key that never reuses the client-supplied
    filename directly — avoids path traversal and cross-upload
    collisions in the shared bucket, while keeping the original
    extension for content-sniffing convenience."""
    return f"{uuid4()}{Path(filename).suffix}"


class FileService:
    """Upload/download use cases: store the file's bytes in S3, keep its
    metadata in Postgres, and keep the two in sync."""

    def __init__(self, file_repository: FileRepository) -> None:
        self._file_repository = file_repository

    async def upload_file(self, filename: str, content_type: str, data: bytes) -> File:
        storage_key = _generate_storage_key(filename)
        logger.debug(
            "uploading file",
            # `filename` collides with a reserved `LogRecord` attribute
            # (the source file of the log call) — `logging` raises
            # `KeyError` if `extra` tries to overwrite it.
            extra={"uploaded_filename": filename, "storage_key": storage_key},
        )
        try:
            await s3_upload_file(storage_key, data, content_type)
        except Exception as exc:
            logger.error(
                "file upload failed",
                extra={"uploaded_filename": filename, "error_type": type(exc).__name__},
            )
            raise

        # `pypdf`/`python-docx`/`openpyxl` are sync libraries and can be
        # CPU-heavy on large files — run off the event loop, same
        # reasoning as sync tool functions inside `invoke_with_tools()`
        # (see `docs/tool-calling.md`). Never fails the upload: parser
        # failures come back as `parse_status="failed"`, not an exception.
        extracted_text, parse_status = await asyncio.to_thread(
            parse_to_text, content_type, data
        )

        file = await self._file_repository.create(
            FileCreate(
                filename=filename,
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
                extracted_text=extracted_text,
                parse_status=parse_status,
            )
        )
        logger.info(
            "file uploaded",
            extra={
                "file_id": file.id,
                "uploaded_filename": filename,
                "size_bytes": len(data),
                "parse_status": parse_status,
            },
        )
        return file

    async def get_metadata(self, file_id: int) -> File:
        """Return `File` metadata without touching S3 — for endpoints
        that only need `extracted_text`/`parse_status`/etc., not the
        raw bytes (`download_file()` below is for that)."""
        file = await self._file_repository.get_by_id(file_id)
        if file is None:
            raise StoredFileNotFoundError(file_id)
        return file

    async def download_file(self, file_id: int) -> tuple[File, bytes]:
        file = await self._file_repository.get_by_id(file_id)
        if file is None:
            raise StoredFileNotFoundError(file_id)

        try:
            data = await s3_download_file(file.storage_key)
        except Exception as exc:
            logger.error(
                "file download failed",
                extra={"file_id": file_id, "error_type": type(exc).__name__},
            )
            raise
        logger.info(
            "file downloaded", extra={"file_id": file_id, "size_bytes": len(data)}
        )
        return file, data
