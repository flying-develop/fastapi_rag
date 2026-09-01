"""Repository for `DialogMessage` — the only DB access point for dialog
history within the `dialog` module (see `.ai-factory/rules/base.md`)."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dialog.models.dialog_message import DialogMessage
from app.modules.dialog.schemas.dialog_message import DialogMessageCreate

logger = logging.getLogger(__name__)


class DialogMessageRepository:
    """Append-and-read access to `dialog_messages` via a request-scoped
    `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, data: DialogMessageCreate) -> DialogMessage:
        message = DialogMessage(
            dialog_id=data.dialog_id, role=data.role, content=data.content
        )
        self._session.add(message)
        await self._session.flush()
        logger.info(
            "dialog message appended",
            extra={
                "message_id": message.id,
                "dialog_id": message.dialog_id,
                "role": message.role,
            },
        )
        return message

    async def list_by_dialog(self, dialog_id: int) -> list[DialogMessage]:
        result = await self._session.execute(
            select(DialogMessage)
            .where(DialogMessage.dialog_id == dialog_id)
            .order_by(DialogMessage.created_at.asc())
        )
        return list(result.scalars().all())
