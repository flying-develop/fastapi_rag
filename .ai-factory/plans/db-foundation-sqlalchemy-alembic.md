# Implementation Plan: Фундамент БД — SQLAlchemy engine/session + Alembic

Branch: none (git отключён в этом проекте)
Created: 2026-08-31

## Original Request
full — первый план из вехи "Фундамент работы с БД" (.ai-factory/ROADMAP.md): SQLAlchemy 2.0 async engine/session + Alembic-миграции (без модуля dialog пока — это будет отдельным следующим планом внутри этой же вехи, по договорённости бить веху на несколько последовательных планов)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes  # обязательный чекпоинт документации в /aif-implement после завершения

## Roadmap Linkage
Milestone: "Фундамент работы с БД"
Rationale: первый из нескольких последовательных планов этой вехи — закладывает инфраструктуру подключения к БД (async engine/session, `get_db()`, Alembic) без доменных моделей; модуль `dialog` со сквозным CRUD будет отдельным следующим планом внутри той же вехи.

## Commit Plan
<!-- git.enabled = false в этом проекте, коммитов не будет — чекпоинты ниже фиксируют логическую группировку задач -->
- **Чекпоинт 1** (после задач 1-3): "feat: add async sqlalchemy engine/session infrastructure"
- **Чекпоинт 2** (после задач 4-5): "feat: setup alembic migrations"
- **Чекпоинт 3** (после задач 6-7): "test: cover db infrastructure and verify migration flow"

## Tasks

### Phase 1: Инфраструктура SQLAlchemy (async engine/session)
- [x] Task 1: Добавить зависимости для работы с БД и тестов через `uv add`: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pytest`, `pytest-asyncio`.
  - Файлы: `pyproject.toml`, `uv.lock`.
  - Логирование: не требуется (шаг установки зависимостей), проверить `uv sync` без ошибок.
- [x] Task 2: Создать `app/infrastructure/db.py`: `Base` (декларативный класс `DeclarativeBase`), async `engine` через `create_async_engine(settings.database_url)`, `async_sessionmaker` (`expire_on_commit=False`), FastAPI-зависимость `get_db()` (async generator, session per request, commit/rollback/close в `try/except/finally`). (зависит от 1)
  - Файлы: `app/infrastructure/db.py`.
  - ЛОГИРОВАНИЕ: DEBUG при создании сессии и при её закрытии (успех/rollback), ERROR при исключении в сессии с полным контекстом (тип исключения). Формат как в `app/infrastructure/logging.py`: `key=value`.
- [x] Task 3: Подключить проверку соединения с БД к `lifespan` в `app/main.py` — при старте выполнить лёгкий `SELECT 1` через `engine`, залогировать успех/неудачу; при неудаче не падать (веха про сами эндпоинты БД ещё впереди), просто ERROR-лог. (зависит от 2)
  - Файлы: `app/main.py`.
  - ЛОГИРОВАНИЕ: INFO при успешной проверке соединения, ERROR с деталями при неудаче.
<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Alembic-миграции
- [x] Task 4: Инициализировать Alembic с async-шаблоном (`alembic init -t async migrations`), настроить `migrations/env.py`: читать `DATABASE_URL` из `Settings` (не из `alembic.ini`), `target_metadata = Base.metadata` из `app/infrastructure/db.py`. (зависит от 3)
  - Файлы: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`.
  - ЛОГИРОВАНИЕ: не требуется (инструмент миграций логирует сам через свой logging.ini), убедиться, что `migrations/` не конфликтует с `app/infrastructure/logging.py` (root-логгер настраивается только в `setup_logging()`).
- [x] Task 5: Создать baseline-миграцию (`alembic revision --autogenerate -m "baseline"` — на этом этапе пустая, т.к. моделей ещё нет) и проверить `upgrade head` / `downgrade base` против Postgres из docker-compose. (зависит от 4)
  - Файлы: `migrations/versions/<rev>_baseline.py`.
  - Проверка: `docker compose up -d postgres`, `uv run alembic upgrade head`, `uv run alembic downgrade base`, `docker compose down`.
<!-- Commit checkpoint: tasks 4-5 -->

### Phase 3: Тесты и сквозная проверка
- [x] Task 6: Настроить pytest (`[tool.pytest.ini_options]` в `pyproject.toml`, `asyncio_mode = "auto"`) и написать тесты для `app/infrastructure/db.py`: `get_db()` отдаёт рабочую `AsyncSession`, сессия корректно закрывается, rollback при исключении внутри блока. Тесты подключаются к Postgres из docker-compose (реальная БД, без моков — согласно правилу "окружение только через Docker"). (зависит от 2)
  - Файлы: `tests/infrastructure/test_db.py`, `pyproject.toml`.
  - ЛОГИРОВАНИЕ: тесты используют существующий `setup_logging()` на DEBUG, чтобы в выводе pytest были видны логи сессий при отладке падений.
- [x] Task 7: Сквозная проверка всей вехи-плана: `docker compose up -d postgres`, `uv run alembic upgrade head`, `uv run pytest`, проверить `/health` и лог старта приложения (успешный `SELECT 1`), `docker compose down`. (зависит от 3, 5, 6)
  - Файлы: нет новых файлов, только проверка.
<!-- Commit checkpoint: tasks 6-7 -->
