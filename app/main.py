"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.requests import Request

from app.infrastructure.config import get_settings
from app.infrastructure.db import engine
from app.infrastructure.logging import setup_logging
from app.infrastructure.s3 import ensure_bucket_exists
from app.modules.dialog.api.router import router as dialog_router
from app.modules.dialog.exceptions import DialogNotFoundError
from app.modules.files.api.router import router as files_router
from app.modules.files.exceptions import StoredFileNotFoundError

logger = logging.getLogger(__name__)


async def _check_db_connection() -> None:
    """Run a lightweight `SELECT 1` to verify DB connectivity at startup.

    Non-fatal: this milestone only sets up the DB infrastructure, no
    endpoint depends on it yet, so a failure is logged as ERROR and
    startup continues rather than crashing the application.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database connection check passed")
    except Exception as exc:
        logger.error(
            "database connection check failed",
            extra={"error_type": type(exc).__name__, "error": str(exc)},
        )


async def _check_s3_bucket() -> None:
    """Ensure the configured S3/MinIO bucket exists at startup.

    Non-fatal, same reasoning as `_check_db_connection()`: a failure here
    (e.g. MinIO not reachable yet) is logged as ERROR and startup
    continues rather than crashing the application.
    """
    try:
        await ensure_bucket_exists()
        logger.info("s3 bucket check passed")
    except Exception as exc:
        logger.error(
            "s3 bucket check failed",
            extra={"error_type": type(exc).__name__, "error": str(exc)},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.debug(
        "application starting",
        extra={"app_name": settings.app_name, "log_level": settings.log_level},
    )
    await _check_db_connection()
    await _check_s3_bucket()
    logger.debug("health endpoint ready", extra={"path": "/health"})
    yield
    await engine.dispose()
    logger.debug("application shutting down")


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

app.include_router(dialog_router)
logger.info("router registered", extra={"prefix": dialog_router.prefix})

app.include_router(files_router)
logger.info("router registered", extra={"prefix": files_router.prefix})


@app.exception_handler(DialogNotFoundError)
async def handle_dialog_not_found(
    request: Request, exc: DialogNotFoundError
) -> JSONResponse:
    """Point handler for a single domain exception — not the unified
    ApiProblemType-style error format, which is a later milestone
    ("Устойчивость и наблюдаемость")."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(StoredFileNotFoundError)
async def handle_file_not_found(
    request: Request, exc: StoredFileNotFoundError
) -> JSONResponse:
    """Point handler, same reasoning as `handle_dialog_not_found()` above."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    logger.debug("health check requested")
    return {"status": "ok"}
