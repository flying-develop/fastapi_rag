"""Use cases orchestrating `Dialog`/`DialogMessage` with the LLM."""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.modules.dialog.exceptions import DialogNotFoundError
from app.modules.dialog.models.dialog_message import DialogMessage
from app.modules.dialog.repositories.dialog_message_repository import (
    DialogMessageRepository,
)
from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog_message import DialogMessageCreate

logger = logging.getLogger(__name__)

_ROLE_TO_MESSAGE_CLASS: dict[str, type[BaseMessage]] = {
    "user": HumanMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
}


def _to_langchain_messages(messages: list[DialogMessage]) -> list[BaseMessage]:
    return [_ROLE_TO_MESSAGE_CLASS[m.role](content=m.content) for m in messages]


class DialogService:
    """Send-message use case: persist the user's message, ask the LLM for
    a reply with the full dialog history, persist and return the reply."""

    def __init__(
        self,
        dialog_repository: DialogRepository,
        message_repository: DialogMessageRepository,
        chat_model: BaseChatModel,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._message_repository = message_repository
        self._chat_model = chat_model

    async def send_message(self, dialog_id: int, text: str) -> DialogMessage:
        dialog = await self._dialog_repository.get_by_id(dialog_id)
        if dialog is None:
            raise DialogNotFoundError(dialog_id)

        history = await self._message_repository.list_by_dialog(dialog_id)
        user_message = await self._message_repository.append(
            DialogMessageCreate(dialog_id=dialog_id, role="user", content=text)
        )

        langchain_messages = _to_langchain_messages([*history, user_message])
        logger.debug(
            "invoking chat model",
            extra={"dialog_id": dialog_id, "history_length": len(langchain_messages)},
        )
        try:
            response = await self._chat_model.ainvoke(langchain_messages)
        except Exception as exc:
            logger.error(
                "chat model call failed",
                extra={"dialog_id": dialog_id, "error_type": type(exc).__name__},
            )
            raise
        logger.debug(
            "chat model responded",
            extra={"dialog_id": dialog_id, "response_length": len(str(response.content))},
        )

        return await self._message_repository.append(
            DialogMessageCreate(
                dialog_id=dialog_id, role="assistant", content=str(response.content)
            )
        )
