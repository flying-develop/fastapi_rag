"""Async SQLAlchemy engine, session factory and FastAPI DB dependency."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models across modules.

    Every module's `models/` package must import this `Base` so that
    `target_metadata` in Alembic's `migrations/env.py` sees all tables.
    """


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session.

    Commits on success, rolls back on any exception raised while the
    session is in use, and always closes the session afterwards.
    """
    session = async_session_factory()
    logger.debug("db session opened", extra={"session_id": id(session)})
    try:
        yield session
        await session.commit()
        logger.debug("db session committed", extra={"session_id": id(session)})
    except Exception as exc:
        await session.rollback()
        logger.error(
            "db session rolled back",
            extra={"session_id": id(session), "error_type": type(exc).__name__},
        )
        raise
    finally:
        await session.close()
        logger.debug("db session closed", extra={"session_id": id(session)})
