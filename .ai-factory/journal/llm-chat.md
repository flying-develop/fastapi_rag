# Журнал реализации: Диалоги с LLM (базовый чат)

Веха roadmap: «Диалоги с LLM (базовый чат)»
Планы вехи:
- `.ai-factory/plans/llm-chat-dialog-message.md` — модель `DialogMessage` + расширение репозитория (реализован, 7/7)
- Следующий план (не начат): LangChain-интеграция (`app/infrastructure/llm.py`), `DialogService`, API-эндпоинт отправки сообщения

## План 1: DialogMessage — модель и репозиторий

### Task 1 — Модель `DialogMessage`

- `app/modules/dialog/models/dialog_message.py` — `DialogMessage(Base)`, таблица `dialog_messages`: `id`, `dialog_id` (`ForeignKey("dialogs.id")`), `role` (`str`, значения `user`/`assistant`/`system` задокументированы в докстринге, без DB-constraint), `content` (`Text`, не `varchar` — сообщения могут быть длинными), `created_at` (`server_default=func.now()`). Без `relationship()` — репозиторный доступ, как у `Dialog`.

### Task 2 — Pydantic-схемы

- `app/modules/dialog/schemas/dialog_message.py` — `DialogMessageCreate` (`dialog_id`, `role: Literal["user", "assistant", "system"]`, `content`), `DialogMessageRead` (все поля, `from_attributes=True`).

### Task 3 — `DialogMessageRepository`

- `app/modules/dialog/repositories/dialog_message_repository.py` — конструктор принимает `AsyncSession`. Методы: `append` (создаёт + `flush`, `INFO`-лог с `message_id`/`dialog_id`/`role`), `list_by_dialog` (сортировка `created_at asc` — хронологический порядок, в отличие от `DialogRepository.list_by_user`, который сортирует `desc`).

**Чекпоинт коммита (после задач 1-3) пропущен** — `git.enabled: false`.

### Task 4 — Alembic-миграция `dialog_messages`

- Обе ловушки из прошлого плана (`db-foundation-dialog-module`) применены превентивно, без повторного отлова:
  - `from app.modules.dialog.models.dialog_message import DialogMessage  # noqa: F401` добавлен в `migrations/env.py` **до** генерации ревизии — autogenerate сразу нашёл `dialog_messages` (`Detected added table 'dialog_messages'`), пустой миграции не было.
  - Образ пересобирался (`docker compose build app`) перед каждым `alembic upgrade head` после генерации файла на хосте.
- Генерация через bind-mount + `busybox chown`, как и раньше.
- Docker-volume `postgres_data` с прошлой сессии уже содержал применённые миграции `baseline`/`add dialogs table` — `alembic upgrade head` перед генерацией новой ревизии не потребовал отдельного восстановления состояния.
- Проверка цикла: `upgrade head` (`3322351eeac7 -> 6a116c1781a1`) → `downgrade -1` → `current` (`3322351eeac7`) → `upgrade head` — отработало чисто. Миграция включает `ForeignKeyConstraint(['dialog_id'], ['dialogs.id'])`.

### Task 5 — Тесты репозитория

- `tests/modules/dialog/test_dialog_message_repository.py`, 4 теста: `append` персистит сообщение, `list_by_dialog` в хронологическом порядке, пустой список без сообщений, изоляция между диалогами (`dialog_id`-фильтрация).
- `dialog_messages.dialog_id` — FK на `dialogs.id`, поэтому каждый тест сначала создаёт `Dialog` через `DialogRepository` (хелпер `_create_dialog`), затем работает с `DialogMessageRepository`.
- Тот же приём для детерминированной проверки хронологического порядка, что и в `test_dialog_repository.py`: явный `UPDATE dialog_messages SET created_at = created_at - interval '1 hour' WHERE id = :id` для более раннего сообщения (Postgres `now()` фиксирован на время транзакции).
- Использована существующая фикстура `tests/conftest.py::db_session` без изменений — `asyncio_default_fixture_loop_scope`/`asyncio_default_test_loop_scope` уже настроены в прошлом плане, новых event-loop проблем не возникло.
- 15/15 тестов проходят (11 старых + 4 новых), запуск только через Docker.

**Чекпоинт коммита (после задач 4-7) пропущен** — `git.enabled: false`.

### Task 6 — Документация (обязательный чекпоинт)

- Выбор пользователя: отдельная страница `docs/dialog-message.md` (не раздел в существующем `docs/dialog.md`, как это было для самого модуля `dialog` в предыдущем плане — прецедент не универсальный, каждый раз уточняется у пользователя).
- Обновлены перекрёстные ссылки: `docs/dialog.md` (nav-заголовок + See Also), `README.md` (таблица документации + пункт в «Возможности»), `AGENTS.md` (дерево структуры, таблица ключевых точек входа, таблица документации).

### Task 7 — Сквозная проверка

- Компиляция/импорт новых модулей — ok. TODO/FIXME/debug-маркеров нет.
- `docker compose run --rm app uv run pytest` — 15/15 passed.
- `alembic current` — `6a116c1781a1 (head)`.
- `docker compose up -d --build` — полный стек, `app`/`postgres` healthy, `curl /health` → `200 OK`.
- `docker compose down` — root-owned файлов не осталось.

**Итог плана:** первый план вехи «Диалоги с LLM (базовый чат)» реализован — модель `DialogMessage` и репозиторий истории сообщений готовы поверх модуля `dialog`. LangChain-интеграция, `DialogService` и API-эндпоинт отправки сообщения — следующий план(ы) той же вехи; веха ещё не закрыта.

## /aif-verify + /aif-review — пост-план

- `/aif-verify` прошла чисто, 7/7, единственный non-blocking WARN — тот же известный Rules gate WARN про `Request`/`Response`-суффиксы (не зафиксирован в RULES.md).
- `/aif-review` нашла 1 блокирующую проблему: `dialog_messages.dialog_id` FK был без `ondelete=` (Postgres по умолчанию `RESTRICT`), а `DialogRepository.delete()` не проверял и не обрабатывал наличие связанных сообщений — удаление диалога с историей падало с необработанным `IntegrityError`. Плюс предложение: нет индекса на `dialog_id`, хотя `list_by_dialog` — это ровно `WHERE dialog_id = ...` запрос.
- **Исправлено сразу** (миграция ещё не была ни у кого применена, кроме локального volume — правился тот же файл ревизии, а не добавлялась новая):
  - `app/modules/dialog/models/dialog_message.py`: `ForeignKey("dialogs.id", ondelete="CASCADE")` + `Index("ix_dialog_messages_dialog_id_created_at", "dialog_id", "created_at")` через `__table_args__`.
  - `migrations/versions/6a116c1781a1_add_dialog_messages_table.py`: `ondelete='CASCADE'` в `ForeignKeyConstraint`, добавлен `op.create_index(...)`.
  - Локальная БД: `alembic downgrade -1` → `alembic upgrade head` (таблица уже существовала со старым FK, отредактированный файл ревизии сам по себе БД не меняет — нужно было переприменить).
  - Новый тест `test_deleting_a_dialog_cascades_its_message_history` в `test_dialog_message_repository.py` — 16/16 тестов проходят.
  - `docs/dialog-message.md` обновлён (раздел «Модель» и «Миграция»).
- Полная сквозная проверка повторена после фикса: `docker compose up -d --build` → healthy, `docker compose down` — без root-owned файлов.
