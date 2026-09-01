"""Tests for `DialogMessageRepository` — real PostgreSQL from
docker-compose, no mocks (see `tests/conftest.py`)."""

from sqlalchemy import text

from app.modules.dialog.repositories.dialog_message_repository import (
    DialogMessageRepository,
)
from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog import DialogCreate
from app.modules.dialog.schemas.dialog_message import DialogMessageCreate

# `dialog_messages.dialog_id` has `ondelete="CASCADE"` — deleting a dialog
# must delete its message history with it, not raise an IntegrityError
# (found via /aif-review: this used to be unhandled).


async def _create_dialog(db_session, user_id: int = 1, title: str = "Test dialog"):
    return await DialogRepository(db_session).create(
        DialogCreate(user_id=user_id, title=title)
    )


async def test_append_persists_message(db_session) -> None:
    dialog = await _create_dialog(db_session)
    repo = DialogMessageRepository(db_session)

    message = await repo.append(
        DialogMessageCreate(dialog_id=dialog.id, role="user", content="Hello")
    )

    assert message.id is not None
    assert message.dialog_id == dialog.id
    assert message.role == "user"
    assert message.content == "Hello"
    assert message.created_at is not None


async def test_list_by_dialog_returns_messages_in_chronological_order(db_session) -> None:
    dialog = await _create_dialog(db_session)
    repo = DialogMessageRepository(db_session)

    first = await repo.append(
        DialogMessageCreate(dialog_id=dialog.id, role="user", content="First")
    )
    # `now()` is fixed for the duration of a Postgres transaction (same
    # pitfall as in test_dialog_repository.py) — backdate the first
    # message so the chronological-order assertion is deterministic.
    await db_session.execute(
        text("UPDATE dialog_messages SET created_at = created_at - interval '1 hour' WHERE id = :id"),
        {"id": first.id},
    )
    second = await repo.append(
        DialogMessageCreate(dialog_id=dialog.id, role="assistant", content="Second")
    )

    messages = await repo.list_by_dialog(dialog.id)

    assert [m.id for m in messages] == [first.id, second.id]


async def test_list_by_dialog_returns_empty_list_when_no_messages(db_session) -> None:
    dialog = await _create_dialog(db_session)
    repo = DialogMessageRepository(db_session)

    assert await repo.list_by_dialog(dialog.id) == []


async def test_list_by_dialog_does_not_return_other_dialogs_messages(db_session) -> None:
    dialog_a = await _create_dialog(db_session, title="Dialog A")
    dialog_b = await _create_dialog(db_session, title="Dialog B")
    repo = DialogMessageRepository(db_session)

    message_a = await repo.append(
        DialogMessageCreate(dialog_id=dialog_a.id, role="user", content="For A")
    )
    await repo.append(
        DialogMessageCreate(dialog_id=dialog_b.id, role="user", content="For B")
    )

    messages = await repo.list_by_dialog(dialog_a.id)

    assert [m.id for m in messages] == [message_a.id]


async def test_deleting_a_dialog_cascades_its_message_history(db_session) -> None:
    dialog = await _create_dialog(db_session)
    message_repo = DialogMessageRepository(db_session)
    await message_repo.append(
        DialogMessageCreate(dialog_id=dialog.id, role="user", content="Hi")
    )

    deleted = await DialogRepository(db_session).delete(dialog.id)

    assert deleted is True
    assert await message_repo.list_by_dialog(dialog.id) == []
