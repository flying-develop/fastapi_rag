# Журнал реализации: Tool calling у LLM (Pydantic-инструменты)

Веха roadmap: «Tool calling у LLM (Pydantic-инструменты)»
Планы вехи:
- `.ai-factory/plans/tool-calling-llm.md` — переиспользуемый паттерн + пример инструмента (реализован, 7/7). Единственный план вехи — реализует весь заявленный скоуп, веха закрыта.

## /aif-improve — до реализации

Перед `/aif-implement` план прогнан через `/aif-improve`. Найдено и применено:
- Task 1: исполнение инструмента с невалидными/упавшими args не было обёрнуто в try/except (в отличие от уже обработанного случая "неизвестный инструмент") — необработанное исключение дошло бы до `DialogService`'s `except Exception` и превратилось в сырой `500`. Добавлена та же graceful-деградация, что и для неизвестного инструмента.
- Task 1: шаг с добавлением `ToolMessage` мутировал бы входной список `messages` вызывающей стороны — для "переиспользуемого хелпера" это плохой контракт. Исправлено на построение нового списка (`extended = [*messages, response]`).
- Task 1: если финальный (второй) ответ модели сам содержит `tool_calls` (вложенный tool call — вне скоупа плана), это никак не логировалось. Добавлен `WARN`.
- Task 4 → Task 5 зависимость исправлена: `FakeChatModel`-расширение зависит от Task 1 (контракт `invoke_with_tools`), а не от Task 3 (wiring в `DialogService`, никак не связан).
- Task 5: добавлены два новых теста под пункты выше (`test_invoke_with_tools_handles_tool_execution_error_gracefully`, `test_invoke_with_tools_does_not_mutate_input_messages_list`).

## План 1: Переиспользуемый паттерн + пример инструмента

### Task 1 — `invoke_with_tools()`

- `app/infrastructure/llm.py`: один раунд tool calling — `bind_tools` → `ainvoke` → если есть `tool_calls`, выполнить каждый (с try/except на `tool.ainvoke`, graceful text-ошибка при сбое или неизвестном имени) → `ToolMessage` в новый список сообщений → повторный `ainvoke`. `WARN`, если финальный ответ снова содержит `tool_calls`.
- Возвращаемый тип — `AIMessage` (не расплывчатый `BaseMessage`) — точнее отражает то, что реально возвращает `chat_model.ainvoke()`.

### Task 2 — `get_current_time`

- `app/modules/dialog/services/tools.py` — `@tool`-функция с одним параметром `timezone: str = "UTC"`, `zoneinfo` (stdlib, без новых зависимостей). Невалидный timezone → текстовая ошибка, не исключение.

**Чекпоинт коммита (после задач 1-2) пропущен** — `git.enabled: false`.

### Task 3 — Wiring в `DialogService`

- Прямой `self._chat_model.ainvoke(...)` заменён на `invoke_with_tools(self._chat_model, DIALOG_TOOLS, langchain_messages)`. Промежуточные tool-calling сообщения сознательно не персистятся в `dialog_messages` — в истории БД только финальный текстовый ответ, как и раньше.

### Task 4 — Расширение `FakeChatModel`

- `tests/modules/dialog/conftest.py`: добавлен `bind_tools()` (заглушка, возвращает `self`) и опциональный `responses: list[AIMessage] | None` — если передан, `ainvoke` отдаёт элементы по очереди. Без `responses` поведение не изменилось — все существующие тесты (`test_dialog_service.py`, `test_dialog_router.py`) прошли без правок.

### Task 5 — Тесты

- `tests/infrastructure/test_llm.py` (новый) — 5 тестов `invoke_with_tools()` напрямую: без tool_calls, успешный tool call, неизвестный инструмент, ошибка выполнения инструмента, отсутствие мутации входного списка.
- **Отловленный вопрос, не проблема**: `FakeChatModel` живёт в `tests/modules/dialog/conftest.py`, а тестировать `invoke_with_tools()` нужно из `tests/infrastructure/` (хелпер dialog-агностичный). Решение — прямой импорт класса (`from tests.modules.dialog.conftest import FakeChatModel`), не через pytest-фикстуру (фикстуры conftest.py не видны сиблинг-директориям). Проверено: работает — `tests/`/`tests/modules/`/`tests/modules/dialog/` без `__init__.py` резолвятся как implicit namespace packages (PEP 420), `pythonpath = ["."]` уже был в конфиге.
- `tests/modules/dialog/test_dialog_service.py` — `test_send_message_uses_tool_result_in_final_reply`: сквозной сценарий с `get_current_time` через реальные репозитории + скриптованный `FakeChatModel`.
- `tests/modules/dialog/test_tools.py` — юнит-тесты `get_current_time` (валидный/дефолтный/невалидный timezone), без LLM.
- Итог: 30/30 тестов (21 старых + 9 новых) проходят.

### Task 6 — Документация (обязательный чекпоинт)

- Выбор пользователя: отдельная страница `docs/tool-calling.md` (алгоритм `invoke_with_tools`, как добавлять новый инструмент, пример `get_current_time`, ограничение на один раунд, персистентность истории, тесты).
- Обновлены перекрёстные ссылки: `docs/dialog-chat.md`, `README.md`, `AGENTS.md` (дерево структуры, таблица точек входа, таблица документации).

### Task 7 — Сквозная проверка

- Компиляция/импорт — ok. TODO/FIXME/debug-маркеров нет. `docker compose run --rm app uv run pytest` — 30/30 passed. Alembic не менялся (миграций в этом плане нет).
- `docker compose up -d --build` — полный стек healthy, `curl /health` → `200 OK`. Без реального `OPENAI_API_KEY` реальный tool-calling запрос к OpenAI вручную не проверялся (как и в прошлом плане) — покрытие через тесты со скриптованной моделью (30/30, включая tool-calling сценарии).
- `docker compose down` — root-owned файлов не осталось.

**Итог плана и вехи:** веха «Tool calling у LLM (Pydantic-инструменты)» закрыта одним планом. Переиспользуемый хелпер `invoke_with_tools()` готов к использованию будущими модулями (RAG-поиск, БД-запросы, внешние API) на следующих вехах — им нужно только определить свой список инструментов. Следующая веха по `ROADMAP.md`: «Диалог как граф LangGraph».
