"""FastAPI routes for the `dialog` module.

Only input validation (Pydantic) and calling the service — no business
logic and no direct DB access here (see `.ai-factory/rules/base.md`).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import get_db
from app.infrastructure.llm import get_chat_model
from app.modules.dialog.repositories.dialog_message_repository import (
    DialogMessageRepository,
)
from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog_message import (
    DialogMessageCreateRequest,
    DialogMessageResponse,
)
from app.modules.dialog.services.dialog_service import DialogService

router = APIRouter(prefix="/dialogs", tags=["dialog"])


def get_dialog_service(session: AsyncSession = Depends(get_db)) -> DialogService:
    return DialogService(
        dialog_repository=DialogRepository(session),
        message_repository=DialogMessageRepository(session),
        chat_model=get_chat_model(),
    )


@router.post(
    "/{dialog_id}/messages",
    response_model=DialogMessageResponse,
    status_code=201,
)
async def send_message(
    dialog_id: int,
    payload: DialogMessageCreateRequest,
    service: DialogService = Depends(get_dialog_service),
) -> DialogMessageResponse:
    message = await service.send_message(dialog_id, payload.content)
    return DialogMessageResponse.model_validate(message)
