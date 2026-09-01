# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Install uv (pinned via the official distroless image, copied as a static binary)
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

# Install dependencies first so this layer is cached while only app code changes.
# This is a --no-package (app-style) uv project: there is no project build step,
# `uv sync` only needs to materialize the .venv from the lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini
COPY tests/ ./tests/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
