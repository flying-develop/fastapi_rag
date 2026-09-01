"""Tests for `POST /dialogs/{dialog_id}/messages` — real Postgres from
docker-compose, fake chat model at the LLM boundary (see
`tests/modules/dialog/conftest.py`).

Uses `httpx.AsyncClient` + `ASGITransport` rather than
`fastapi.testclient.TestClient`: `TestClient` runs the app through its
own sync-bridging portal/thread, which risks the same "different event
loop" class of bug this project has hit twice already with the shared
`engine`/`db_session` (see `pyproject.toml`'s `asyncio_default_*_loop_scope`
comments). `AsyncClient` + `ASGITransport` runs entirely on the current
test's event loop instead.
"""

import httpx
import pytest

from app.main import app
from app.modules.dialog.api.router import get_dialog_service
from app.modules.dialog.repositories.dialog_message_repository import (
    DialogMessageRepository,
)
from app.modules.dialog.repositories.dialog_repository import DialogRepository
from app.modules.dialog.schemas.dialog import DialogCreate
from app.modules.dialog.services.dialog_service import DialogService


@pytest.fixture
async def client(db_session, fake_chat_model):
    def _override() -> DialogService:
        return DialogService(
            dialog_repository=DialogRepository(db_session),
            message_repository=DialogMessageRepository(db_session),
            chat_model=fake_chat_model,
        )

    # Overrides get_dialog_service entirely (bypassing get_db) so the
    # request reuses the test's own db_session — a separate session
    # opened via get_db() wouldn't see rows the test only flushed
    # (never committed) in its own transaction.
    app.dependency_overrides[get_dialog_service] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.pop(get_dialog_service, None)


async def test_post_message_returns_201_with_assistant_reply(
    client, db_session, fake_chat_model
) -> None:
    dialog = await DialogRepository(db_session).create(
        DialogCreate(user_id=1, title="Test dialog")
    )

    response = await client.post(
        f"/dialogs/{dialog.id}/messages", json={"content": "Hello"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"] == fake_chat_model.reply
    assert body["dialog_id"] == dialog.id


async def test_post_message_returns_404_for_missing_dialog(client) -> None:
    response = await client.post("/dialogs/999999/messages", json={"content": "Hello"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Dialog 999999 not found"
