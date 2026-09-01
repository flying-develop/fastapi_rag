# Журнал реализации: Фундамент работы с БД

Веха roadmap: «Фундамент работы с БД»
Планы вехи:
- `.ai-factory/plans/db-foundation-sqlalchemy-alembic.md` — SQLAlchemy engine/session + Alembic (реализован, 7/7)
- `.ai-factory/plans/db-foundation-dialog-module.md` — модуль `dialog` со сквозным CRUD через repository-паттерн (реализован, 7/7). Второй и последний план вехи — веха закрыта.

## План 1: SQLAlchemy engine/session + Alembic

### Task 1 — Зависимости

- `uv add "sqlalchemy[asyncio]" asyncpg alembic` — в основные зависимости.
- `uv add --dev pytest pytest-asyncio` — в dev-группу (`[dependency-groups] dev`), а не в основные зависимости, как было в тексте плана буквально: тестовые инструменты не нужны в проде. Отклонение сознательное и безопасное — `uv sync --frozen` в Dockerfile по умолчанию ставит dev-группу тоже, так что pytest доступен и в образе.

### Task 2 — `app/infrastructure/db.py`

- `Base(DeclarativeBase)` — общий декларативный класс для ORM-моделей всех модулей.
- `engine = create_async_engine(settings.database_url, pool_pre_ping=True)` — создаётся при импорте модуля (как и `Settings` в `config.py`), но **не подключается** при этом (ленивая инициализация драйвера) — импорт модуля успешен даже без доступной БД.
- `async_session_factory` — `async_sessionmaker(expire_on_commit=False)`.
- `get_db()` — FastAPI-зависимость (async generator): commit при успехе, rollback при исключении, close всегда в `finally`. DEBUG-логи на открытие/коммит/закрытие сессии, ERROR — на rollback с типом исключения.

### Task 3 — Проверка соединения в `lifespan`

- `_check_db_connection()` в `app/main.py`: `SELECT 1` через `engine.connect()`, INFO при успехе, ERROR (нефатально) при неудаче — эта веха не завязывает на БД ни один эндпоинт, поэтому падать при недоступной БД не нужно.
- Также добавил `await engine.dispose()` на shutdown в `lifespan` (не было явно в задаче, но логично закрывать пул соединений при остановке приложения).
- Проверка без БД (вне docker-сети, хост не резолвит `postgres`): DNS-резолвинг падает примерно за 10 секунд (`gaierror: Temporary failure in name resolution`), логируется ERROR, приложение всё равно поднимается и отвечает на `/health`. Ожидаемо, что внутри docker-сети таких задержек не будет (либо резолвится сразу, либо мгновенный connection refused).

**Чекпоинт коммита (после задач 1-3) пропущен** — `git.enabled: false` в проекте.

### Task 4 — Инициализация Alembic

- `uv run alembic init -t async migrations` — async-шаблон.
- `migrations/env.py`: URL берётся из `Settings.database_url` (`config.set_main_option("sqlalchemy.url", ...)`), а не из `alembic.ini` — миграции всегда бьют в ту же БД, что и приложение. `target_metadata = Base.metadata` из `app/infrastructure/db.py`.
- Проверено запуском `uv run alembic current` без доступной БД — дошло до попытки подключения (та же ошибка DNS-резолвинга), что подтверждает корректную загрузку конфигурации и `target_metadata`.

### Task 5 — Baseline-миграция и проверка upgrade/downgrade

- **Отклонение от буквального текста плана**: чтобы `docker compose run` мог создавать/применять миграции против реального Postgres из docker-compose, в `Dockerfile` добавлены `COPY migrations/ ./migrations/`, `COPY alembic.ini ./alembic.ini` и `COPY tests/ ./tests/` (плана впрямую не касалось, но без этого образ приложения не мог бы работать с Alembic/pytest — необходимо для соблюдения принципа "всё через Docker").
- `docker compose up -d postgres` → дождался `healthy`.
- `docker compose build app` — с новыми COPY-слоями.
- `docker compose run --rm app uv run alembic revision --autogenerate -m "baseline"` — **первая попытка не сработала**: `docker compose run --rm` удаляет контейнер после выхода, а `migrations/` не примонтирован как volume, поэтому сгенерированный файл пропал вместе с контейнером. Исправлено через одноразовый bind-mount: `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "baseline"` — файл появился на хосте. Модели ещё не существуют, поэтому `upgrade()`/`downgrade()` в миграции пустые (ожидаемо).
- Файл миграции создался с владельцем `root` (процесс в контейнере запущен от root) — хост не даёт `chown` без sudo, поэтому владелец исправлен через одноразовый `docker run --rm -v ...:/mnt busybox chown -R 1000:1000 ...` и удалён случайный `__pycache__/` внутри `migrations/versions/`.
- Пересобрал образ (чтобы миграция попала в образ через `COPY migrations/`), затем: `alembic upgrade head` → `alembic current` (head) → `alembic downgrade base` → `alembic current` (пусто) — цикл отработал чисто на реальном Postgres. В конце снова накатил `upgrade head`, чтобы БД была готова для тестов/финальной проверки.

**Чекпоинт коммита (после задач 4-5) пропущен** — `git.enabled: false`.

### Task 6 — pytest

- `pyproject.toml` → `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `pythonpath = ["."]` (без `pythonpath` тесты в `tests/infrastructure/` без `__init__.py` не находили пакет `app` — `ModuleNotFoundError: No module named 'app'`; добавление `pythonpath = ["."]` проще, чем расставлять `__init__.py` по всему `tests/`).
- `tests/infrastructure/test_db.py`, 4 теста: engine коннектится к БД из `Settings`, `get_db()` отдаёт рабочую сессию, коммит при успехе (по DEBUG-логам через `caplog`), rollback при исключении (`gen.athrow(...)`).
- **Отловленная и исправленная проблема**: при дефолтном (per-test) event loop в pytest-asyncio второй тест падал с `RuntimeError: ... attached to a different loop` — модуль-level `engine` создаётся один раз на процесс и его connection pool переиспользует соединения между тестами, а каждое соединение "привязано" к тому event loop, в котором было открыто. Фикс — `asyncio_default_test_loop_scope = "session"` в pytest ini: единый event loop на всю тестовую сессию, соответствующий времени жизни модуль-level `engine`. Задокументировано комментарием в `pyproject.toml`.
- Все тесты запускаются только через Docker: `docker compose run --rm app uv run pytest` (реальная БД, без моков — согласно правилу проекта об окружении только в Docker). 4/4 passed.

### Task 7 — Сквозная проверка

- `docker compose up -d --build` — полный стек, `app`/`postgres` healthy.
- Лог `app` показал `msg="database connection check passed"` — успешная проверка `SELECT 1` при старте (позитивный сценарий, в отличие от Task 3, где проверялся негативный вне docker-сети).
- `curl http://localhost:8000/health` → `200 OK`.
- `docker compose down` — стек остановлен, volumes (включая накаченную `postgres_data` с применённой baseline-миграцией) не тронуты.

**Итог плана:** инфраструктура подключения к БД готова и проверена (engine/session, Alembic upgrade/downgrade, тесты на реальном Postgres из Docker). Моделей и репозиториев ещё нет — это следующий план той же вехи (`dialog`-модуль).

## План 2: Модуль dialog (модели, репозиторий, схемы)

### Побочная задача перед началом — смена кредов Postgres

Между планами пользователь попросил заменить терминологию `kwork` → `проекты`/`projects` по всему проекту, включая дефолтные креды Postgres (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`DATABASE_URL`: `kwork` → `projects`) в `docker-compose.yml`, `.env.example`, `app/infrastructure/config.py`, `docs/configuration.md`. Так как volume `ai-app-python_postgres_data` из Плана 1 был уже инициализирован под старого пользователя `kwork`, а локальный `.env` тоже содержал старые креды — перед началом Task 4 (миграция) обновил `.env` на `projects`/`projects` и выполнил `docker compose down -v` (сброс volumes; данных на тот момент не было — только baseline-миграция).

### Task 1 — Модель `Dialog`

- `app/modules/dialog/models/dialog.py` — `Dialog(Base)`, таблица `dialogs`: `id`, `user_id` (без FK — модуля пользователей ещё нет), `title`, `created_at`/`updated_at` (`server_default=func.now()`, `updated_at` дополнительно `onupdate=func.now()`).

### Task 2 — Pydantic-схемы

- `app/modules/dialog/schemas/dialog.py` — `DialogCreate` (`user_id`, `title`), `DialogUpdate` (`title`), `DialogRead` (все поля, `ConfigDict(from_attributes=True)`).

**Чекпоинт коммита (после задач 1-2) пропущен** — `git.enabled: false`.

### Task 3 — `DialogRepository`

- `app/modules/dialog/repositories/dialog_repository.py` — конструктор принимает `AsyncSession`. Методы: `create`, `get_by_id`, `list_by_user` (сортировка `created_at desc`), `update`, `delete` (оба возвращают `None`/`False`, если диалог не найден). Только `flush()`, коммит — снаружи в `get_db()`. `INFO`-логи на create/update/delete (уровень логирования плана — `standard`).

### Task 4 — Alembic-миграция `dialogs`

- **Отловленная и исправленная проблема**: первая попытка `alembic revision --autogenerate` сгенерировала пустую миграцию (`upgrade()`/`downgrade()` — `pass`) — `Dialog` не попал в `Base.metadata`, потому что `migrations/env.py` никогда не импортирует модели модулей, а SQLAlchemy регистрирует класс на `Base.metadata` только при реальном импорте модуля. Исправлено добавлением `from app.modules.dialog.models.dialog import Dialog  # noqa: F401` в `migrations/env.py` с комментарием, что каждый новый модуль должен добавлять свой импорт сюда для autogenerate. После этого автогенерация корректно нашла `dialogs`.
- Тот же паттерн bind-mount + chown, что и в Плане 1 (`docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "add dialogs table"`, затем `busybox chown`).
- **Ещё одна отловленная деталь**: после генерации миграции `alembic upgrade head` без пересборки образа показал старый head (`df364b45a5ac`) — `Dockerfile` копирует `migrations/` в образ на этапе сборки, поэтому новый файл миграции виден в контейнере только после `docker compose build app`. Пересобрал образ, затем `upgrade head` применился корректно (`df364b45a5ac -> 3322351eeac7`).
- Проверка цикла: `downgrade -1` → `current` (пусто/база) → `upgrade head` — отработало чисто.

**Чекпоинт коммита (после задач 3-4) пропущен** — `git.enabled: false`.

### Task 5 — Тесты репозитория

- Первый `tests/conftest.py` в проекте: фикстура `db_session` — сессия из `async_session_factory()`, изоляция между тестами через `rollback()` в конце (не `TRUNCATE`) — репозиторий только `flush()`ит, коммита никогда не происходит внутри теста, так что откат надёжно чистит все записи.
- `tests/modules/dialog/test_dialog_repository.py`, 7 тестов: create, get_by_id (найден/не найден), list_by_user (фильтрация по `user_id` + сортировка desc), update (найден/не найден), delete (найден/не найден).
- Для детерминированной проверки сортировки по `created_at desc` в одной тестовой транзакции: Postgres `now()` фиксирован на время всей транзакции, поэтому два `flush()` подряд получили бы одинаковый `created_at`. Решение — явный `UPDATE dialogs SET created_at = created_at - interval '1 hour' WHERE id = :id` для более раннего диалога перед созданием второго, вместо изменения дефолта модели.
- **Отловленная и исправленная проблема** (новая разновидность бага из Плана 1): первый прогон тестов падал в teardown фикстуры `db_session` с `RuntimeError: ... attached to a different loop` — несмотря на уже выставленный в Плане 1 `asyncio_default_test_loop_scope = "session"`. Причина: это первая async-фикстура в проекте, а async-фикстуры pytest-asyncio управляются **отдельной** настройкой `asyncio_default_fixture_loop_scope` (по умолчанию — своя область видимости, не совпадающая с `asyncio_default_test_loop_scope`), из-за чего фикстура открывала сессию в одном event loop, а pool `engine` был привязан к другому. Фикс — `asyncio_default_fixture_loop_scope = "session"` в `pyproject.toml`, с комментарием. После фикса 11/11 тестов (4 старых + 7 новых) проходят.
- Запуск только через Docker: `docker compose run --rm app uv run pytest`.

### Task 6 — Документация (обязательный чекпоинт)

- Выбор пользователя: отдельная страница `docs/dialog.md` (модель, схемы, репозиторий, миграция, тесты, включая заметку про `env.py`-импорт для autogenerate и про `asyncio_default_fixture_loop_scope`).
- Обновлены перекрёстные ссылки: `docs/db.md` (nav-заголовок + See Also), `docs/getting-started.md` (See Also), `README.md` (таблица документации + пункт в «Возможности»), `AGENTS.md` (дерево структуры, таблица ключевых точек входа, таблица документации).

### Task 7 — Сквозная проверка

- Компиляция/импорт новых модулей — ok. TODO/FIXME/debug-маркеров нет.
- `docker compose run --rm app uv run pytest` — 11/11 passed.
- `alembic current` — `3322351eeac7 (head)`.
- `docker compose up -d --build` — полный стек, `app`/`postgres` healthy, `curl /health` → `200 OK`, лог `database connection check passed`.
- `docker compose down` — без сохранения volumes на этот раз (в отличие от Плана 1, здесь это не требовалось отдельно проверять). Проверка на root-owned файлы в рабочей директории — не найдено.

### Побочная задача после реализации — удаление упоминаний Laravel/«учебного переноса» из документации

Отдельно от этого плана пользователь попросил убрать все упоминания «учебный перенос»/Laravel из пользовательской и внутренней документации (README.md, AGENTS.md, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`, `.ai-factory/rules/base.md`, журнал вехи «Bootstrap проекта»). Проектная рамка теперь — самостоятельный AI-сервис на FastAPI + LangChain/LangGraph, без ссылок на референсный Laravel-проект как источник происхождения. Сохранена содержательная часть (архитектурные решения, обоснование паттерна модулей, конкретные milestone-описания) — убрана только рамка «перенос/аналог из Laravel». Замечание в память: Laravel-проект по-прежнему используется как поведенческий референс при планировании/реализации — просто не упоминается в md-файлах.

**Итог плана:** веха «Фундамент работы с БД» закрыта — оба плана реализованы и верифицированы (engine/session + Alembic из Плана 1, первый доменный модуль `dialog` с repository-паттерном из Плана 2). Паттерн репозитория и структура модуля задокументированы как образец для `rag`/`tasks`/`moderation`/`files` на следующих вехах.
