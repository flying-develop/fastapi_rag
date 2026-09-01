"""Shared pytest fixtures.

Tests run against the real PostgreSQL instance from docker-compose (no
mocks, per project convention). See `docs/db.md` / `AGENTS.md` for the
Docker-only test invocation.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import async_session_factory


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """A session scoped to a single test, isolated via rollback.

    Repository code only `flush()`es (commit happens in `get_db()`, the
    FastAPI dependency, not in the repository itself) — so rolling back
    at teardown discards every write the test made, without needing to
    truncate tables between tests.
    """
    async with async_session_factory() as session:
        yield session
        await session.rollback()
