# DialogMessage: модель и расширение репозитория

Branch: none
Created: 2026-09-01

## Original Request

Первый план новой вехи «Диалоги с LLM (базовый чат)» (см. .ai-factory/ROADMAP.md). Веха описана как: модели Dialog/DialogMessage, интеграция с LangChain chat-моделью (OpenAI), эндпоинт отправки сообщения с сохранением истории в PostgreSQL. Модель Dialog и repository-паттерн уже готовы (веха «Фундамент работы с БД», модуль dialog). Этот план — первый из нескольких последовательных планов вехи: модель DialogMessage (SQLAlchemy) + расширение repository-слоя модуля dialog для истории сообщений (схемы, CRUD/append для DialogMessage, миграция). LangChain-интеграция, сервисный слой и API-эндпоинт — это следующий(е) план(ы) той же вехи, не этот.

## Settings

- Testing: yes — тесты репозитория на реальном Postgres из docker-compose, без моков
- Logging: standard — INFO для ключевых событий репозитория
- Docs: yes — обязательный чекпоинт документации по завершении (`/aif-docs`)

## Roadmap Linkage

Milestone: "Диалоги с LLM (базовый чат)"

Rationale: первый из нескольких последовательных планов вехи. Добавляет модель `DialogMessage` и репозиторий для истории сообщений поверх уже готового модуля `dialog` (вехa «Фундамент работы с БД»). LangChain-интеграция, `DialogService` и API-эндпоинт отправки сообщения — вне скоупа, это следующий план(ы) той же вехи. Веха не отмечается выполненной до завершения всех её планов.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-3): модель `DialogMessage` + схемы + репозиторий.
   `feat(dialog): add DialogMessage model and repository`
2. **Checkpoint 2** (Tasks 4-7): миграция, тесты, документация, финальная проверка.
   `feat(dialog): add dialog_messages migration; test(dialog): add message repository tests; docs(dialog): document message history`

## Tasks

### Phase 1: Модель, схемы, репозиторий

- [x] **Task 1: SQLAlchemy-модель `DialogMessage`**
  - Создать `app/modules/dialog/models/dialog_message.py`.
  - Класс `DialogMessage(Base)` (импорт `Base` из `app/infrastructure/db.py`), таблица `dialog_messages`:
    - `id: Mapped[int]` — primary key, autoincrement
    - `dialog_id: Mapped[int]` — `mapped_column(ForeignKey("dialogs.id"))`
    - `role: Mapped[str]` — ожидаемые значения `"user"`/`"assistant"`/`"system"`, задокументировать в докстринге (без DB-level enum/constraint на этом этапе — валидация роли будет на уровне Pydantic-схемы в Task 2)
    - `content: Mapped[str]` — `mapped_column(Text)` (не varchar — сообщения могут быть длинными)
    - `created_at: Mapped[datetime]` — `server_default=func.now()`
  - Без ORM-`relationship()` к `Dialog` — репозиторный доступ, как и у существующего `Dialog` (см. `app/modules/dialog/models/dialog.py`).
  - Логирование не требуется (декларативная модель).

- [x] **Task 2: Pydantic-схемы (DTO) для `DialogMessage`**
  - Создать `app/modules/dialog/schemas/dialog_message.py`.
  - `DialogMessageCreate` — `dialog_id: int`, `role: Literal["user", "assistant", "system"]`, `content: str`.
  - `DialogMessageRead` — `id`, `dialog_id`, `role`, `content`, `created_at`, `model_config = ConfigDict(from_attributes=True)`.
  - Зависит от Task 1 (использует те же имена полей).

- [x] **Task 3: `DialogMessageRepository`**
  - Создать `app/modules/dialog/repositories/dialog_message_repository.py`.
  - Класс `DialogMessageRepository`, конструктор принимает `AsyncSession` (тот же паттерн, что и `DialogRepository`).
  - Методы:
    - `async def append(self, data: DialogMessageCreate) -> DialogMessage` — создаёт, `session.add` + `flush` (коммит — снаружи, в `get_db()`), лог `INFO` с `message_id`/`dialog_id`/`role` после `flush`.
    - `async def list_by_dialog(self, dialog_id: int) -> list[DialogMessage]` — отсортировано по `created_at asc` (хронологический порядок для истории диалога, в отличие от `list_by_user` в `DialogRepository`, который сортирует `desc`).
  - Логирование: `INFO` на `append`, без DEBUG на `list_by_dialog`.
  - Зависит от Task 1, Task 2.

### Phase 2: Миграция, тесты, документация, проверка

- [x] **Task 4: Alembic-миграция для таблицы `dialog_messages`**
  - **Важно** (отловлено в предыдущем плане): `migrations/env.py` собирает `target_metadata` из `Base.metadata`, но модель регистрируется на нём только если её модуль реально импортирован — добавить `from app.modules.dialog.models.dialog_message import DialogMessage  # noqa: F401` в `migrations/env.py` **до** генерации ревизии, иначе autogenerate создаст пустую миграцию.
  - Через Docker с bind-mount (см. `docs/db.md`):
    `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "add dialog_messages table"`.
  - `down_revision` должен указывать на текущий head (ревизия из плана `db-foundation-dialog-module`, таблица `dialogs`).
  - **Важно** (отловлено в предыдущем плане): после генерации файла на хосте пересобрать образ (`docker compose build app`) перед `alembic upgrade head` — Dockerfile копирует `migrations/` на этапе сборки, `docker compose run` без bind-mount видит только старую версию.
  - Проверить сгенерированный файл вручную (FK на `dialogs.id`, `Text` для `content`), поправить владельца файла при необходимости (root → host user).
  - Применить: `docker compose run --rm app uv run alembic upgrade head`, проверить `downgrade -1` + повторный `upgrade head`.
  - Зависит от Task 1.

- [x] **Task 5: Тесты репозитория**
  - Создать `tests/modules/dialog/test_dialog_message_repository.py`.
  - Используется существующая фикстура `tests/conftest.py::db_session` (транзакция + rollback между тестами).
  - `dialog_messages.dialog_id` — FK на `dialogs.id`, поэтому каждый тест сначала создаёт `Dialog` через `DialogRepository` (тот же паттерн, что и в `test_dialog_repository.py`), затем работает с `DialogMessageRepository` для этого `dialog_id`.
  - Тесты (реальный Postgres из docker-compose, без моков):
    - `test_append_persists_message`
    - `test_list_by_dialog_returns_messages_in_chronological_order`
    - `test_list_by_dialog_returns_empty_list_when_no_messages`
    - `test_list_by_dialog_does_not_return_other_dialogs_messages`
  - Зависит от Task 3, Task 4 (нужна применённая миграция).

- [x] **Task 6: Документация (обязательный чекпоинт)**
  - Через `/aif-docs`: дополнить `docs/dialog.md` разделом про `DialogMessage` (модель, схемы, репозиторий, миграция, тесты) — по аналогии с существующими разделами про `Dialog`. Уточнить у пользователя на чекпоинте, если стоит выделить отдельную страницу вместо дополнения существующей.
  - Обновить `AGENTS.md` (структура проекта) при необходимости.
  - Зависит от Task 1-5 (документируется финальное состояние).

- [x] **Task 7: Финальная проверка**
  - Полный прогон тестов в Docker: `docker compose up -d postgres`, `docker compose run --rm app uv run pytest`.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Проверить состояние Alembic: `docker compose run --rm app uv run alembic current` — должен быть head новой ревизии.
  - Опустить стек (`docker compose down`), убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-6.
