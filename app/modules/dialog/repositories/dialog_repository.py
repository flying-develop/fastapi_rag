"""Repository for the `Dialog` model — the only DB access point for the
`dialog` module (see `.ai-factory/rules/base.md`)."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dialog.models.dialog import Dialog
from app.modules.dialog.schemas.dialog import DialogCreate, DialogUpdate

logger = logging.getLogger(__name__)


class DialogRepository:
    """CRUD access to `dialogs` via a request-scoped `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: DialogCreate) -> Dialog:
        dialog = Dialog(user_id=data.user_id, title=data.title)
        self._session.add(dialog)
        await self._session.flush()
        logger.info(
            "dialog created", extra={"dialog_id": dialog.id, "user_id": dialog.user_id}
        )
        return dialog

    async def get_by_id(self, dialog_id: int) -> Dialog | None:
        result = await self._session.execute(
            select(Dialog).where(Dialog.id == dialog_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[Dialog]:
        result = await self._session.execute(
            select(Dialog)
            .where(Dialog.user_id == user_id)
            .order_by(Dialog.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, dialog_id: int, data: DialogUpdate) -> Dialog | None:
        dialog = await self.get_by_id(dialog_id)
        if dialog is None:
            return None
        dialog.title = data.title
        await self._session.flush()
        logger.info("dialog updated", extra={"dialog_id": dialog_id})
        return dialog

    async def delete(self, dialog_id: int) -> bool:
        dialog = await self.get_by_id(dialog_id)
        if dialog is None:
            return False
        await self._session.delete(dialog)
        await self._session.flush()
        logger.info("dialog deleted", extra={"dialog_id": dialog_id})
        return True
