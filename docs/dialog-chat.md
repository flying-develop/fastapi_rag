[← DialogMessage](dialog-message.md) · [Back to README](../README.md) · [Tool calling у LLM →](tool-calling.md)

# Диалоги с LLM: базовый чат

Второй и последний план вехи «Диалоги с LLM (базовый чат)» — LangChain
chat-модель, `DialogService` и первый API-эндпоинт проекта:
`POST /dialogs/{dialog_id}/messages`. Поверх модуля `dialog` (модель,
репозитории — см. [Модуль dialog](dialog.md), [DialogMessage](dialog-message.md)).

## LangChain chat-модель

`app/infrastructure/llm.py`:

- `get_chat_model()` — `@lru_cache`-фабрика, возвращает `ChatOpenAI`,
  но типизирована как провайдер-нейтральный `BaseChatModel` — вызывающий
  код (`DialogService`) не зависит от конкретного провайдера, замена на
  Gemini/Qwen позже не требует переписывать `DialogService`
  (см. `.ai-factory/DESCRIPTION.md`).
- Модель и ключ берутся из `Settings` (`OPENAI_CHAT_MODEL`,
  `OPENAI_API_KEY`) — см. [Конфигурация](configuration.md).
- Клиент `ChatOpenAI` проверяет наличие ключа **при создании** — без
  `OPENAI_API_KEY` вызов `get_chat_model()` падает с
  `openai.OpenAIError: Missing credentials`. В приложении это происходит
  лениво (внутри `get_dialog_service`, при первом запросе к эндпоинту),
  не при старте — `/health` и остальные части приложения работают без
  ключа.

## `DialogService`

`app/modules/dialog/services/dialog_service.py` — `send_message(dialog_id, text) -> DialogMessage`:

1. Найти `Dialog` по `dialog_id`; если не найден — `DialogNotFoundError`.
2. Прочитать историю сообщений (`DialogMessageRepository.list_by_dialog`).
3. Сохранить сообщение пользователя (`role="user"`).
4. Сконвертировать историю + новое сообщение в LangChain-сообщения
   (`role` → `HumanMessage`/`AIMessage`/`SystemMessage`) и вызвать
   `chat_model.ainvoke(...)`.
5. Сохранить и вернуть ответ ассистента (`role="assistant"`).

LangGraph здесь **не используется** — прямой линейный вызов LLM. Перевод
на граф состояний — отдельная веха «Диалог как граф LangGraph»
(следующая после Tool calling по `ROADMAP.md`).

## API-эндпоинт

`app/modules/dialog/api/router.py` — первый роут проекта помимо `/health`.

**`POST /dialogs/{dialog_id}/messages`**

```bash
curl -X POST http://localhost:8000/dialogs/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Привет!"}'
```

Успех (`201`):

```json
{
  "id": 2,
  "dialog_id": 1,
  "role": "assistant",
  "content": "Привет! Чем могу помочь?",
  "created_at": "2026-09-01T12:00:00Z"
}
```

Диалог не найден (`404`):

```json
{"detail": "Dialog 1 not found"}
```

Запрос принимает только `content` — `role` не задаётся клиентом:
`DialogService` всегда сохраняет входящие через API сообщения как
`role="user"`, чтобы нельзя было подделать `"assistant"`/`"system"`
сообщение в истории. Схемы — `DialogMessageCreateRequest`/
`DialogMessageResponse` в `app/modules/dialog/schemas/dialog_message.py`
(суффиксы `Request`/`Response` — по конвенции `.ai-factory/rules/base.md`
для схем API-слоя, в отличие от внутренних DTO репозитория
`DialogMessageCreate`/`DialogMessageRead`).

Обработка ошибок — точечный `@app.exception_handler(DialogNotFoundError)`
в `app/main.py` (`404`), не единый формат `ApiProblemType` — тот появится
на вехе «Устойчивость и наблюдаемость».

## Конфигурация

См. также [Конфигурация](configuration.md).

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OPENAI_API_KEY` | — (пусто) | Ключ OpenAI; без него эндпоинт возвращает `500` при первом запросе |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Название модели OpenAI |

## Тесты

`tests/modules/dialog/test_dialog_service.py`,
`tests/modules/dialog/test_dialog_router.py` — реальный Postgres из
docker-compose (без моков БД), но **фейковая** chat-модель на границе
LLM (`tests/modules/dialog/conftest.py::FakeChatModel`) — реальные
вызовы OpenAI в тестах не делаются, ключ не нужен.

Тесты эндпоинта используют `httpx.AsyncClient` + `ASGITransport`, а не
`fastapi.testclient.TestClient` — `TestClient` прогоняет запрос через
отдельный поток/portal, что рискует повторить уже дважды пойманный в
этом проекте класс багов "разные event loop" для общего `engine`/
`db_session` (см. комментарии `asyncio_default_*_loop_scope` в
`pyproject.toml`). `AsyncClient` с `ASGITransport` выполняется в том же
event loop, что и сам тест.

## See Also

- [Модуль dialog](dialog.md) — модель `Dialog`, `DialogRepository`
- [DialogMessage](dialog-message.md) — модель и репозиторий истории
- [Tool calling у LLM](tool-calling.md) — `invoke_with_tools`, пример-инструмент `get_current_time`
- [Конфигурация](configuration.md) — `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules
