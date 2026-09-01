# Журнал реализации: Диалоги с LLM (базовый чат)

Веха roadmap: «Диалоги с LLM (базовый чат)»
Планы вехи:
- `.ai-factory/plans/llm-chat-dialog-message.md` — модель `DialogMessage` + расширение репозитория (реализован, 7/7)
- `.ai-factory/plans/llm-chat-service-endpoint.md` — LangChain-интеграция, `DialogService`, API-эндпоинт (реализован, 10/10). Второй и последний план вехи — веха закрыта.

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

## План 2: LangChain-интеграция, DialogService, эндпоинт отправки сообщения

### Task 1 — Зависимости и конфигурация

- `uv add langchain langchain-openai` — **отклонение от предыдущего плана**: запускал через `docker compose run --rm app uv add ...` (по инерции "всё через Docker"), но `--rm` удаляет контейнер вместе с изменениями в `pyproject.toml`/`uv.lock` — тот же класс проблемы, что и с генерацией миграций. Изменения не попали на хост. Исправлено запуском `uv add` напрямую на хосте (`uv` установлен: `/home/user/.local/bin/uv`) — редактирование манифеста зависимостей не требует поднятого окружения (БД/Redis/Qdrant), это не "запуск сервиса", поэтому не подпадает под правило "только через Docker"; тот же способ, судя по всему, использовался и в самом первом плане вехи «Фундамент работы с БД».
- `httpx` пришёл транзитивно через `openai`/`langchain` (виден в `uv.lock`) — отдельно как dev-зависимость не добавлял, как и было предусмотрено в тексте плана.
- `app/infrastructure/config.py`: `openai_chat_model: str = "gpt-4o-mini"`. `.env.example` и `.env`: `OPENAI_CHAT_MODEL=gpt-4o-mini`.

### Task 2 — `app/infrastructure/llm.py`

- `get_chat_model()` (`@lru_cache`) — `ChatOpenAI(model=..., api_key=...)`, типизирован как `BaseChatModel`.
- Смоук-тест без ключа подтвердил ожидаемое поведение: `ChatOpenAI` проверяет наличие ключа **при создании клиента** (`openai.OpenAIError: Missing credentials`), не при первом реальном вызове. Это происходит лениво — только при обращении к `get_dialog_service` (Task 6), не при старте приложения.

**Чекпоинт коммита (после задач 1-2) пропущен** — `git.enabled: false`.

### Task 3 — `DialogNotFoundError`

- `app/modules/dialog/exceptions.py` — простое доменное исключение с `dialog_id` и читаемым сообщением.

### Task 4 — `DialogService`

- `app/modules/dialog/services/dialog_service.py` — `send_message(dialog_id, text)`: найти диалог (иначе `DialogNotFoundError`) → прочитать историю → сохранить сообщение пользователя → сконвертировать историю+новое сообщение в LangChain-сообщения (`role` → `HumanMessage`/`AIMessage`/`SystemMessage`) → `chat_model.ainvoke(...)` → сохранить и вернуть ответ ассистента.
- LangGraph сознательно не используется — прямой линейный вызов, как и предписывал `ROADMAP.md` (граф — отдельная веха позже).
- Небольшая правка по ходу дела относительно текста плана: вместо создания отдельного "черновика" `DialogMessage` для конвертации в LangChain-сообщения переиспользуется объект, уже возвращённый `message_repository.append()` — чище, без лишнего объекта.

**Чекпоинт коммита (после задач 3-4) пропущен** — `git.enabled: false`.

### Task 5 — API-схемы

- `DialogMessageCreateRequest` (только `content`), `DialogMessageResponse(DialogMessageRead)` — публичное имя для API-контракта. Закрывает Rules gate WARN, тянувшийся с верификации Плана 1 этой вехи (`Request`/`Response`-суффиксы теперь есть там, где действительно есть API-слой).

### Task 6 — `app/modules/dialog/api/router.py`

- `get_dialog_service(session=Depends(get_db))` собирает `DialogRepository`, `DialogMessageRepository`, `get_chat_model()`. `POST /dialogs/{dialog_id}/messages`, `status_code=201`, `response_model=DialogMessageResponse`.

### Task 7 — Wiring в `app/main.py`

- `app.include_router(dialog_router)`, `@app.exception_handler(DialogNotFoundError)` → `404 {"detail": ...}` (точечный handler, не единый `ApiProblemType`-формат — тот на отдельной вехе).
- Смоук-тест через `TestClient` с фейковым `OPENAI_API_KEY`: `POST /dialogs/999999/messages` → `404 {"detail": "Dialog 999999 not found"}` — маршрут и обработка ошибок работают. Интересная деталь: `app.routes` в установленной версии FastAPI/Starlette не разворачивает включённые роутеры в плоский список (виден `_IncludedRouter`, а не `APIRoute` для `/dialogs/...`) — маршрутизация тем не менее работает корректно, подтверждено реальным HTTP-запросом, а не интроспекцией `app.routes`.

**Чекпоинт коммита (после задач 5-7) пропущен** — `git.enabled: false`.

### Task 8 — Тесты

- `tests/modules/dialog/conftest.py::FakeChatModel` — минимальная замена chat-модели (`async def ainvoke(...) -> AIMessage`), без реальных вызовов OpenAI, записывает все вызовы для проверок.
- `test_dialog_service.py` (3 теста): appends user+assistant, история целиком передаётся в `ainvoke`, `DialogNotFoundError` при отсутствующем диалоге.
- `test_dialog_router.py` (2 теста) — **важное архитектурное решение**: использован `httpx.AsyncClient` + `ASGITransport` вместо `fastapi.testclient.TestClient`. `TestClient` прогоняет запрос через отдельный поток/portal — рискует повторить уже дважды пойманный в этой вехе класс багов "другой event loop" для общего `engine`/`db_session`. `AsyncClient`+`ASGITransport` выполняется в том же event loop, что и сам тест — новых event-loop проблем не возникло. `get_dialog_service` переопределяется целиком (`app.dependency_overrides`), а не только chat-модель — иначе запрос открыл бы отдельную сессию через `get_db()`, которая не увидит несохранённые (`flush`, не `commit`) данные тестовой транзакции `db_session`.
- Итог: 21/21 тестов (16 старых + 5 новых) проходят.

### Task 9 — Документация (обязательный чекпоинт)

- Выбор пользователя: отдельная страница `docs/dialog-chat.md` (LangChain, `DialogService`, эндпоинт с примерами запроса/ответа, конфигурация, обработка ошибок, тесты).
- Обновлены перекрёстные ссылки: `docs/dialog-message.md`, `docs/configuration.md` (новая переменная), `README.md` (таблица + «Возможности» + убрано "диалоги с LLM" из списка "остальных" будущих возможностей), `AGENTS.md` (дерево структуры — впервые заполнены `api/`/`services/`, таблица точек входа, таблица документации).

### Task 10 — Сквозная проверка

- Компиляция/импорт — ok. TODO/FIXME/debug-маркеров нет. `docker compose run --rm app uv run pytest` — 21/21 passed. `alembic current` — без изменений (`6a116c1781a1`, этот план моделей не добавлял).
- `docker compose up -d --build` — полный стек healthy. Ручная проверка через `curl` без реального `OPENAI_API_KEY`: `500` (ожидаемо и задокументировано — `ChatOpenAI` требует ключ при создании клиента). Пользователь решил не давать реальный ключ для этой проверки — ограничились прогоном тестов с фейковой моделью (21/21) плюс более ранним smoke-тестом через `TestClient` с фейковым ключом, подтвердившим маршрутизацию и 404-ветку.
- Тестовая строка `dialogs`, созданная вручную для проверки, удалена после проверки. `docker compose down` — без root-owned файлов.

**Итог плана и вехи:** веха «Диалоги с LLM (базовый чат)» закрыта — оба плана реализованы и верифицированы. Модуль `dialog` теперь задействует все слои архитектуры (`api/services/repositories/models/schemas`), первый API-эндпоинт проекта работает end-to-end (кроме реального вызова OpenAI — не проверялся вручную по решению пользователя). Следующая веха по `ROADMAP.md`: «Tool calling у LLM (Pydantic-инструменты)».
