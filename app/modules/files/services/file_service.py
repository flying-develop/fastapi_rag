"""Use cases orchestrating `File` metadata with S3-compatible storage."""

import logging
from pathlib import Path
from uuid import uuid4

from app.infrastructure.s3 import download_file as s3_download_file
from app.infrastructure.s3 import upload_file as s3_upload_file
from app.modules.files.exceptions import StoredFileNotFoundError
from app.modules.files.models.file import File
from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.schemas.file import FileCreate

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

        file = await self._file_repository.create(
            FileCreate(
                filename=filename,
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
            )
        )
        logger.info(
            "file uploaded",
            extra={
                "file_id": file.id,
                "uploaded_filename": filename,
                "size_bytes": len(data),
            },
        )
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
