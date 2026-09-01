# LangChain-интеграция, DialogService, эндпоинт отправки сообщения

Branch: none
Created: 2026-09-01

## Original Request

Второй и последний план вехи «Диалоги с LLM (базовый чат)» (см. .ai-factory/ROADMAP.md, журнал .ai-factory/journal/llm-chat.md). Первый план (модель DialogMessage + расширение репозитория, план llm-chat-dialog-message) уже реализован, верифицирован и закоммичен. Этот план завершает веху: LangChain-интеграция с chat-моделью OpenAI (app/infrastructure/llm.py), DialogService (use case отправки сообщения: сохранить сообщение пользователя, вызвать LLM с историей диалога, сохранить и вернуть ответ ассистента) и API-эндпоинт (POST /dialogs/{id}/messages) с сохранением истории в PostgreSQL через уже готовые DialogRepository/DialogMessageRepository.

## Settings

- Testing: yes — `DialogService` на реальном Postgres (репозитории без моков) с фейковой (не реальной OpenAI) chat-моделью; API-эндпоинт через `TestClient`/`httpx` с override зависимости на ту же фейковую модель
- Logging: verbose — подробные DEBUG-логи на вызов LLM и таймингах ответа, полезно для первой интеграции с внешним API
- Docs: yes — обязательный чекпоинт документации по завершении (`/aif-docs`)

## Roadmap Linkage

Milestone: "Диалоги с LLM (базовый чат)"

Rationale: второй и последний план этой вехи. Первый план добавил модель `DialogMessage` и репозиторий истории. Этот план добавляет недостающие слои — LangChain chat-модель, `DialogService` (оркестрация: сохранить сообщение пользователя → вызвать LLM с историей → сохранить и вернуть ответ ассистента) и первый API-роут проекта (`POST /dialogs/{id}/messages`). По завершении веха «Диалоги с LLM (базовый чат)» полностью закрыта — следующая веха по `ROADMAP.md`: «Tool calling у LLM».

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-2): зависимости + `app/infrastructure/llm.py`.
   `feat(llm): add LangChain chat model factory`
2. **Checkpoint 2** (Tasks 3-4): доменные исключения + `DialogService`.
   `feat(dialog): add DialogService — send_message use case`
3. **Checkpoint 3** (Tasks 5-7): API-схемы, роут, wiring в `main.py`.
   `feat(dialog): add POST /dialogs/{id}/messages endpoint`
4. **Checkpoint 4** (Tasks 8-10): тесты, документация, финальная проверка.
   `test(dialog): add DialogService and endpoint tests; docs(dialog): document chat endpoint`

## Tasks

### Phase 1: LangChain-инфраструктура

- [x] **Task 1: Зависимости и конфигурация**
  - `uv add langchain langchain-openai` — в основные зависимости.
  - `uv add --dev httpx` — для `TestClient`/`AsyncClient` в тестах API-эндпоинта (проверить перед добавлением, не тянется ли уже транзитивно через FastAPI/Starlette — если да, отдельно не добавлять).
  - `app/infrastructure/config.py`: добавить поле `openai_chat_model: str = "gpt-4o-mini"` (имя модели OpenAI, настраивается через `.env`, комментарий в коде — "используется начиная с вехи «Диалоги с LLM»", аналогично существующему `openai_api_key`).
  - `.env.example`: добавить `OPENAI_CHAT_MODEL=gpt-4o-mini` рядом с существующим `OPENAI_API_KEY=`.
  - Логирование не требуется (конфигурация).

- [x] **Task 2: `app/infrastructure/llm.py` — фабрика chat-модели**
  - Создать `app/infrastructure/llm.py`.
  - `get_chat_model() -> BaseChatModel` (`@lru_cache`, тот же паттерн, что и `get_settings()`) — возвращает `ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key)`.
  - Тип возврата — `langchain_core.language_models.BaseChatModel`, а не конкретный `ChatOpenAI`, чтобы вызывающий код (`DialogService`) не зависел от конкретного провайдера — архитектура должна допускать замену на Gemini/Qwen позже без переписывания вызывающего кода (см. `.ai-factory/DESCRIPTION.md`).
  - DEBUG-лог при создании клиента (модель, но не ключ — секрет не логировать).
  - Зависит от Task 1.

### Phase 2: Доменный слой

- [x] **Task 3: Доменное исключение `DialogNotFoundError`**
  - Создать `app/modules/dialog/exceptions.py`.
  - `class DialogNotFoundError(Exception)` — конструктор принимает `dialog_id: int`, сообщение вида `f"Dialog {dialog_id} not found"`, атрибут `self.dialog_id` для дальнейшей обработки в exception handler'е (Task 7).
  - Логирование не требуется (класс исключения).

- [x] **Task 4: `DialogService` — use case отправки сообщения**
  - Создать `app/modules/dialog/services/__init__.py`, `app/modules/dialog/services/dialog_service.py`.
  - Класс `DialogService`, конструктор принимает `dialog_repository: DialogRepository`, `message_repository: DialogMessageRepository`, `chat_model: BaseChatModel` (DI через конструктор — паттерн из `.ai-factory/ARCHITECTURE.md`).
  - `async def send_message(self, dialog_id: int, text: str) -> DialogMessage`:
    1. `dialog = await self._dialog_repository.get_by_id(dialog_id)`; если `None` — `raise DialogNotFoundError(dialog_id)`.
    2. `history = await self._message_repository.list_by_dialog(dialog_id)` (хронологический порядок).
    3. Сохранить сообщение пользователя: `await self._message_repository.append(DialogMessageCreate(dialog_id=dialog_id, role="user", content=text))`.
    4. Конвертировать `history` + новое сообщение пользователя в список LangChain-сообщений (приватный хелпер `_to_langchain_messages`, маппинг `role` → `HumanMessage`/`AIMessage`/`SystemMessage` из `langchain_core.messages`).
    5. `response = await self._chat_model.ainvoke(messages)`.
    6. Сохранить ответ ассистента: `await self._message_repository.append(DialogMessageCreate(dialog_id=dialog_id, role="assistant", content=response.content))` — вернуть этот `DialogMessage`.
  - Логирование: DEBUG перед вызовом LLM (`dialog_id`, число сообщений в истории), DEBUG после (длина ответа, без содержимого — потенциально чувствительные данные пользователя), ERROR с типом исключения при сбое вызова LLM (исключение не глотать — пробрасывать дальше).
  - Зависит от Task 2, Task 3, и уже готовых `DialogRepository`/`DialogMessageRepository` (веха «Фундамент работы с БД»).

### Phase 3: API-слой

- [x] **Task 5: API-схемы (`Request`/`Response`)**
  - Дополнить `app/modules/dialog/schemas/dialog_message.py`.
  - `DialogMessageCreateRequest` — только `content: str` (роль не задаётся клиентом — сервис всегда проставляет `role="user"` для входящих через API сообщений, чтобы нельзя было прислать поддельное `role="assistant"`/`"system"`).
  - `DialogMessageResponse(DialogMessageRead)` — те же поля, публичное имя для API-контракта (именование по конвенции `.ai-factory/rules/base.md`: суффиксы `Request`/`Response` — для схем API-слоя, в отличие от `DialogMessageCreate`/`DialogMessageRead`, которые остаются внутренними DTO репозитория).
  - Зависит от Task 4 (использует `DialogMessage`-поля).

- [x] **Task 6: `app/modules/dialog/api/router.py`**
  - Создать `app/modules/dialog/api/__init__.py`, `app/modules/dialog/api/router.py`.
  - `router = APIRouter(prefix="/dialogs", tags=["dialog"])`.
  - Зависимость `get_dialog_service(session: AsyncSession = Depends(get_db)) -> DialogService` — собирает `DialogRepository(session)`, `DialogMessageRepository(session)`, `get_chat_model()`.
  - `POST /dialogs/{dialog_id}/messages`, `response_model=DialogMessageResponse`, `status_code=201`:
    ```python
    async def send_message(
        dialog_id: int,
        payload: DialogMessageCreateRequest,
        service: DialogService = Depends(get_dialog_service),
    ) -> DialogMessageResponse:
        message = await service.send_message(dialog_id, payload.content)
        return DialogMessageResponse.model_validate(message)
    ```
  - Роут не содержит бизнес-логики — только валидация входа (через Pydantic) и вызов сервиса (см. `.ai-factory/rules/base.md`).
  - Зависит от Task 4, Task 5.

- [x] **Task 7: Wiring в `app/main.py`**
  - `app.include_router(dialog_router)` — первый роут в проекте помимо `/health`.
  - Exception handler для `DialogNotFoundError` → `404` с `{"detail": str(exc)}` (JSONResponse). Единый формат ошибок API (`ApiProblemType`-аналог) — отдельная веха «Устойчивость и наблюдаемость», здесь — точечный handler под конкретное исключение, без забегания вперёд.
  - INFO-лог при регистрации роутера (опционально, по аналогии с существующими лог-сообщениями в `lifespan`).
  - Зависит от Task 3, Task 6.

### Phase 4: Тесты, документация, проверка

- [x] **Task 8: Тесты**
  - `tests/modules/dialog/conftest.py` (или хелпер в существующем `tests/conftest.py`, если уместнее) — простая фейковая chat-модель для тестов: класс/функция с `async def ainvoke(self, messages) -> AIMessage`, возвращающая заранее заданный текст ответа (без реальных вызовов OpenAI — ключ API в тестовом окружении не задан).
  - `tests/modules/dialog/test_dialog_service.py` — `DialogService` на реальном Postgres (через `db_session`/`DialogRepository`/`DialogMessageRepository`, без моков БД) с фейковой chat-моделью:
    - `test_send_message_appends_user_and_assistant_messages`
    - `test_send_message_passes_full_history_to_chat_model` (проверить, что в `ainvoke` передана вся предыдущая история + новое сообщение)
    - `test_send_message_raises_when_dialog_missing`
  - `tests/modules/dialog/test_dialog_router.py` — API-эндпоинт через `TestClient` (или `httpx.AsyncClient` + `ASGITransport`), с `app.dependency_overrides[get_dialog_service]` на фейковую chat-модель, БД — реальный Postgres:
    - `test_post_message_returns_201_with_assistant_reply`
    - `test_post_message_returns_404_for_missing_dialog`
  - Зависит от Task 7.

- [x] **Task 9: Документация (обязательный чекпоинт)**
  - Через `/aif-docs`: описать `app/infrastructure/llm.py`, `DialogService`, эндпоинт `POST /dialogs/{id}/messages` (пример запроса/ответа, `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`). Уточнить у пользователя на чекпоинте — отдельная страница или раздел в существующей документации по dialog-модулю.
  - Обновить `docs/configuration.md` (новая переменная `OPENAI_CHAT_MODEL`), `AGENTS.md` (структура, ключевые точки входа), `README.md` при необходимости.
  - Зависит от Task 1-8 (документируется финальное состояние).

- [x] **Task 10: Финальная проверка**
  - Полный прогон тестов в Docker: `docker compose up -d postgres`, `docker compose run --rm app uv run pytest`.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Ручная проверка через полный стек: `docker compose up -d --build`, `curl -X POST http://localhost:8000/dialogs/<id>/messages ...` — либо с реальным `OPENAI_API_KEY` в `.env` (если пользователь готов дать ключ для ручной проверки), либо ограничиться прогоном тестов с фейковой моделью и явно отметить в журнале, что реальный вызов OpenAI не проверялся вручную.
  - Опустить стек (`docker compose down`), убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-9.
