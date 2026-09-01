"""Tests for `DialogRepository` — real PostgreSQL from docker-compose,
no mocks (see `tests/conftest.py`)."""

from sqlalchemy import text

from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog import DialogCreate, DialogUpdate


async def test_create_persists_dialog(db_session) -> None:
    repo = DialogRepository(db_session)

    dialog = await repo.create(DialogCreate(user_id=1, title="First dialog"))

    assert dialog.id is not None
    assert dialog.user_id == 1
    assert dialog.title == "First dialog"
    assert dialog.created_at is not None


async def test_get_by_id_returns_none_when_missing(db_session) -> None:
    repo = DialogRepository(db_session)

    assert await repo.get_by_id(999_999) is None


async def test_list_by_user_returns_only_that_users_dialogs_ordered_by_created_at_desc(
    db_session,
) -> None:
    repo = DialogRepository(db_session)

    older = await repo.create(DialogCreate(user_id=42, title="Older dialog"))
    # `now()` is fixed for the duration of a Postgres transaction, so two
    # flushes in the same test transaction would otherwise get an
    # identical `created_at`. Backdate the first row explicitly to make
    # the desc-order assertion below deterministic.
    await db_session.execute(
        text("UPDATE dialogs SET created_at = created_at - interval '1 hour' WHERE id = :id"),
        {"id": older.id},
    )
    newer = await repo.create(DialogCreate(user_id=42, title="Newer dialog"))
    await repo.create(DialogCreate(user_id=7, title="Other user's dialog"))

    dialogs = await repo.list_by_user(42)

    assert [d.id for d in dialogs] == [newer.id, older.id]


async def test_update_changes_title(db_session) -> None:
    repo = DialogRepository(db_session)
    dialog = await repo.create(DialogCreate(user_id=1, title="Original title"))

    updated = await repo.update(dialog.id, DialogUpdate(title="New title"))

    assert updated is not None
    assert updated.title == "New title"


async def test_update_returns_none_when_missing(db_session) -> None:
    repo = DialogRepository(db_session)

    assert await repo.update(999_999, DialogUpdate(title="New title")) is None


async def test_delete_removes_dialog_and_returns_true(db_session) -> None:
    repo = DialogRepository(db_session)
    dialog = await repo.create(DialogCreate(user_id=1, title="To be deleted"))

    assert await repo.delete(dialog.id) is True
    assert await repo.get_by_id(dialog.id) is None


async def test_delete_returns_false_when_missing(db_session) -> None:
    repo = DialogRepository(db_session)

    assert await repo.delete(999_999) is False
