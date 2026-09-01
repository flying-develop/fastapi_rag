"""Tests for the async SQLAlchemy engine/session infrastructure.

These tests hit the real PostgreSQL instance from docker-compose (no
mocks, per project convention — the dev environment always runs
through Docker). Run them via:

    docker compose up -d postgres
    docker compose run --rm app uv run pytest
"""

import logging

import pytest
from sqlalchemy import text

from app.infrastructure.db import engine, get_db


async def test_engine_connects_to_the_configured_database() -> None:
    """The engine created from Settings.database_url can reach Postgres."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_get_db_yields_a_working_session() -> None:
    """`get_db()` yields a session that can run queries."""
    gen = get_db()
    session = await anext(gen)

    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1

    # Draining the generator (as FastAPI does after the response is sent)
    # must reach the commit branch and finish cleanly.
    with pytest.raises(StopAsyncIteration):
        await anext(gen)


async def test_get_db_commits_on_success(caplog: pytest.LogCaptureFixture) -> None:
    """No exception raised while consuming the session -> commit, not rollback."""
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.db")

    gen = get_db()
    await anext(gen)
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    assert "db session committed" in caplog.text
    assert "db session rolled back" not in caplog.text


async def test_get_db_rolls_back_on_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exception raised while using the session triggers a rollback, not a commit."""
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.db")

    gen = get_db()
    await anext(gen)

    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    assert "db session rolled back" in caplog.text
    assert "db session committed" not in caplog.text
