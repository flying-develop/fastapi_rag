"""Tests for `DialogService` — real repositories against Postgres from
docker-compose (no mocks), with a fake chat model at the LLM boundary
(no real OpenAI calls; see `tests/modules/dialog/conftest.py`)."""

import pytest
from langchain_core.messages import AIMessage

from app.modules.dialog.exceptions import DialogNotFoundError
from app.modules.dialog.repositories.dialog_message_repository import (
    DialogMessageRepository,
)
from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog import DialogCreate
from app.modules.dialog.schemas.dialog_message import DialogMessageCreate
from app.modules.dialog.services.dialog_service import DialogService
from tests.modules.dialog.conftest import FakeChatModel


def _make_service(db_session, fake_chat_model) -> DialogService:
    return DialogService(
        dialog_repository=DialogRepository(db_session),
        message_repository=DialogMessageRepository(db_session),
        chat_model=fake_chat_model,
    )


async def test_send_message_appends_user_and_assistant_messages(
    db_session, fake_chat_model
) -> None:
    dialog = await DialogRepository(db_session).create(
        DialogCreate(user_id=1, title="Test dialog")
    )
    service = _make_service(db_session, fake_chat_model)

    reply = await service.send_message(dialog.id, "Hello")

    assert reply.role == "assistant"
    assert reply.content == fake_chat_model.reply

    history = await DialogMessageRepository(db_session).list_by_dialog(dialog.id)
    assert [(m.role, m.content) for m in history] == [
        ("user", "Hello"),
        ("assistant", fake_chat_model.reply),
    ]


async def test_send_message_passes_full_history_to_chat_model(
    db_session, fake_chat_model
) -> None:
    dialog = await DialogRepository(db_session).create(
        DialogCreate(user_id=1, title="Test dialog")
    )
    message_repo = DialogMessageRepository(db_session)
    await message_repo.append(
        DialogMessageCreate(dialog_id=dialog.id, role="user", content="Earlier question")
    )
    await message_repo.append(
        DialogMessageCreate(
            dialog_id=dialog.id, role="assistant", content="Earlier answer"
        )
    )
    service = _make_service(db_session, fake_chat_model)

    await service.send_message(dialog.id, "Follow-up")

    assert len(fake_chat_model.calls) == 1
    sent_messages = fake_chat_model.calls[0]
    assert [m.content for m in sent_messages] == [
        "Earlier question",
        "Earlier answer",
        "Follow-up",
    ]


async def test_send_message_raises_when_dialog_missing(
    db_session, fake_chat_model
) -> None:
    service = _make_service(db_session, fake_chat_model)

    with pytest.raises(DialogNotFoundError):
        await service.send_message(999_999, "Hello")

    assert fake_chat_model.calls == []


async def test_send_message_uses_tool_result_in_final_reply(db_session) -> None:
    dialog = await DialogRepository(db_session).create(
        DialogCreate(user_id=1, title="Test dialog")
    )
    fake_chat_model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_current_time",
                        "args": {"timezone": "UTC"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="It is currently around noon UTC."),
        ]
    )
    service = _make_service(db_session, fake_chat_model)

    reply = await service.send_message(dialog.id, "What time is it?")

    assert reply.content == "It is currently around noon UTC."

    history = await DialogMessageRepository(db_session).list_by_dialog(dialog.id)
    assert [(m.role, m.content) for m in history] == [
        ("user", "What time is it?"),
        ("assistant", "It is currently around noon UTC."),
    ]
