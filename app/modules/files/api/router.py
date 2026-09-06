"""FastAPI routes for the `files` module.

Only input validation and calling the service — no business logic and no
direct DB/S3 access here (see `.ai-factory/rules/base.md`).
"""

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import get_db
from app.modules.files.repositories.file_repository import FileRepository
from app.modules.files.schemas.file import FileResponse
from app.modules.files.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])


def get_file_service(session: AsyncSession = Depends(get_db)) -> FileService:
    return FileService(file_repository=FileRepository(session))


@router.post("", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile, service: FileService = Depends(get_file_service)
) -> FileResponse:
    data = await file.read()
    stored = await service.upload_file(
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return FileResponse.model_validate(stored)


@router.get("/{file_id}/metadata", response_model=FileResponse)
async def get_file_metadata(
    file_id: int, service: FileService = Depends(get_file_service)
) -> FileResponse:
    file = await service.get_metadata(file_id)
    return FileResponse.model_validate(file)


@router.get("/{file_id}")
async def download_file(
    file_id: int, service: FileService = Depends(get_file_service)
) -> Response:
    file, data = await service.download_file(file_id)
    return Response(
        content=data,
        media_type=file.content_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
