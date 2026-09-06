"""Repository for the `File` model — the only DB access point for the
`files` module (see `.ai-factory/rules/base.md`)."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models.file import File
from app.modules.files.schemas.file import FileCreate

logger = logging.getLogger(__name__)


class FileRepository:
    """CRUD access to `files` via a request-scoped `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: FileCreate) -> File:
        file = File(
            filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            storage_key=data.storage_key,
            extracted_text=data.extracted_text,
            parse_status=data.parse_status,
        )
        self._session.add(file)
        await self._session.flush()
        logger.info(
            "file metadata created",
            extra={"file_id": file.id, "storage_key": file.storage_key},
        )
        return file

    async def get_by_id(self, file_id: int) -> File | None:
        result = await self._session.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()
