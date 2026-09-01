# Tool calling у LLM: переиспользуемый паттерн + пример инструмента

Branch: none
Created: 2026-09-02

## Original Request

Первый план новой вехи «Tool calling у LLM (Pydantic-инструменты)» (см. .ai-factory/ROADMAP.md). Веха описана как: модель не просто генерирует текст, а вызывает инструменты-функции; параметры и результат вызова описаны Pydantic-схемами (structured output). Базовый паттерн на простом примере — переиспользуется в следующих вехах для получения данных (БД, RAG-поиск, внешние API) и других фич, а не только в диалоге. Реализовать сквозной паттерн tool calling через LangChain (bind_tools, обработка tool_calls в ответе модели, выполнение инструмента, возврат результата модели, финальный ответ) на одном простом самодостаточном примере инструмента без новых внешних зависимостей (например, получение текущего времени), встроенном в существующий DialogService.send_message. Паттерн должен быть переиспользуемым для будущих инструментов на следующих вехах.

## Settings

- Testing: yes — тесты на реальном Postgres (без моков БД), но с расширенной фейковой chat-моделью (без реальных вызовов OpenAI), умеющей отдавать заскриптованные `tool_calls`
- Logging: standard — INFO на каждый вызов инструмента (имя, без полного результата, если он большой)
- Docs: yes — обязательный чекпоинт документации по завершении (`/aif-docs`)

## Roadmap Linkage

Milestone: "Tool calling у LLM (Pydantic-инструменты)"

Rationale: первый план вехи, реализует весь заявленный в вехе скоуп — сквозной паттерн tool calling (bind_tools → обработка tool_calls → выполнение инструмента → финальный ответ) как переиспользуемый хелпер в `app/infrastructure/llm.py`, плюс один самодостаточный пример-инструмент (`get_current_time`), встроенный в `DialogService`. Паттерн явно спроектирован для переиспользования будущими модулями (RAG-поиск, БД-запросы, внешние API) на следующих вехах — им нужно будет только определить свой список `BaseTool` и передать его в тот же хелпер.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-2): переиспользуемый хелпер + пример-инструмент.
   `feat(llm): add invoke_with_tools helper and get_current_time example tool`
2. **Checkpoint 2** (Tasks 3-5): интеграция в DialogService + тесты.
   `feat(dialog): wire tool calling into DialogService.send_message; test: tool-calling coverage`
3. **Checkpoint 3** (Tasks 6-7): документация, финальная проверка.
   `docs(llm): document tool-calling pattern`

## Tasks

### Phase 1: Переиспользуемый паттерн и пример-инструмент

- [x] **Task 1: `invoke_with_tools()` в `app/infrastructure/llm.py`**
  - Добавить `async def invoke_with_tools(chat_model: BaseChatModel, tools: list[BaseTool], messages: list[BaseMessage]) -> BaseMessage`.
  - Логика (один раунд tool calling — без рекурсии/многошаговых агентных циклов, это отдельная веха «Диалог как граф LangGraph»):
    1. `model_with_tools = chat_model.bind_tools(tools) if tools else chat_model`.
    2. `response = await model_with_tools.ainvoke(messages)`.
    3. Если `not response.tool_calls` — вернуть `response` как есть (обратная совместимость: при пустом списке инструментов или отказе модели их вызывать — ровно один `ainvoke`, как раньше).
    4. Иначе — построить **новый** список сообщений (не мутировать входной `messages`, чтобы хелпер оставался чистой функцией для будущих вызывающих модулей): `extended = [*messages, response]`. Для каждого `tool_call` в `response.tool_calls`: найти инструмент по `tool_call["name"]` в `tools`; если не найден — результат `f"Error: unknown tool '{name}'"` (без исключения — модель должна суметь корректно отреагировать текстом); если найден — вызвать `await tool.ainvoke(tool_call["args"])` в `try/except Exception`, при исключении результат — `f"Error: tool '{name}' failed: {exc}"` (WARN в лог, не пробрасывать) — тот же принцип graceful-деградации, что и для неизвестного инструмента, только для случая "инструмент найден, но упал/не принял такие args". Добавить `ToolMessage(content=str(result), tool_call_id=tool_call["id"])` в `extended`.
    5. `final = await model_with_tools.ainvoke(extended)`. Если `final.tool_calls` непусто (модель снова запросила инструмент — многошаговый tool calling вне скоупа этого плана) — залогировать `WARN` (`tool_names` из `final.tool_calls`) перед возвратом; поведение не меняется, только видимость в логах. `return final`.
  - Логирование: INFO на каждый успешно выполненный tool call (`tool_name`, `tool_call_id`), WARN если инструмент не найден, WARN если выполнение инструмента бросило исключение (с типом исключения), WARN если финальный ответ снова содержит `tool_calls`.
  - Импорт `ToolMessage`, `BaseMessage`, `AIMessage` из `langchain_core.messages`, `BaseTool` из `langchain_core.tools`.
  - Зависит от существующего `get_chat_model()` (не меняется).

- [x] **Task 2: Пример-инструмент `get_current_time`**
  - Создать `app/modules/dialog/services/tools.py`.
  - `@tool`-декорированная функция `get_current_time(timezone: str = "UTC") -> str` — docstring описывает назначение и параметр (используется LangChain для генерации Pydantic-схемы аргументов, показывающейся модели). Реализация — `zoneinfo.ZoneInfo(timezone)` (stdlib, без новых зависимостей) + `datetime.now(tz).isoformat()`; при `ZoneInfoNotFoundError` — вернуть `f"Error: unknown timezone '{timezone}'"` (не исключение — та же философия graceful-ошибок, что и в Task 1).
  - `DIALOG_TOOLS: list[BaseTool] = [get_current_time]` — список инструментов модуля `dialog`, экспортируется для использования в `DialogService`.
  - Логирование не требуется (чистая функция).
  - Зависит от Task 1 (типизация `BaseTool`).

### Phase 2: Интеграция и тесты

- [x] **Task 3: Wiring в `DialogService.send_message`**
  - `app/modules/dialog/services/dialog_service.py`: заменить прямой `await self._chat_model.ainvoke(langchain_messages)` на `await invoke_with_tools(self._chat_model, DIALOG_TOOLS, langchain_messages)` (импорт из `app.infrastructure.llm` и `app.modules.dialog.services.tools`).
  - Остальная логика `send_message` (сохранение user-сообщения, финального ответа ассистента) не меняется — промежуточные `AIMessage(tool_calls=...)`/`ToolMessage` **не персистятся** в `dialog_messages` (осознанное упрощение для базового паттерна: в истории БД остаётся только финальный текстовый ответ ассистента, как и раньше; полный tool-calling обмен живёт только в рамках одного вызова `send_message`).
  - try/except вокруг вызова (уже существующий, ловит `Exception`, логирует ERROR, пробрасывает дальше) должен оборачивать вызов `invoke_with_tools`, а не сырой `ainvoke`.
  - Зависит от Task 1, Task 2.

- [x] **Task 4: Расширить `FakeChatModel` под tool calling**
  - `tests/modules/dialog/conftest.py`: добавить `bind_tools(self, tools)` — сохраняет `self.bound_tools = list(tools)`, возвращает `self` (заглушка, не фильтрует реально).
  - Добавить опциональный параметр конструктора `responses: list[AIMessage] | None = None` — если передан, `ainvoke` возвращает элементы по очереди (`.pop(0)`) при каждом вызове вместо фиксированного `self.reply`; если не передан — поведение не меняется (полная обратная совместимость с уже существующими тестами `test_dialog_service.py`/`test_dialog_router.py`, которые полагаются на `.reply`/один `ainvoke`).
  - Зависит от Task 1 (расширение фейка должно соответствовать контракту `invoke_with_tools`: `bind_tools`, число вызовов `ainvoke`) — не от Task 3, wiring в `DialogService` на структуру фейка не влияет.

- [x] **Task 5: Тесты tool calling**
  - `tests/infrastructure/test_llm.py` (новый файл) — тесты `invoke_with_tools()` напрямую с `FakeChatModel` (реального обращения к БД не нужно):
    - `test_invoke_with_tools_returns_first_response_when_no_tool_calls` (0 tool calls → один `ainvoke`, без изменений сообщений)
    - `test_invoke_with_tools_executes_tool_and_returns_final_response` (заскриптованные 2 ответа: первый с `tool_calls`, второй — финальный текст; проверить, что инструмент реально вызван с правильными `args`, что второй `ainvoke` получил `ToolMessage` с правильным `tool_call_id`, и что вернулся именно второй ответ)
    - `test_invoke_with_tools_handles_unknown_tool_gracefully` (заскриптованный `tool_calls` с несуществующим именем — `ToolMessage` с `"Error: unknown tool ..."`, исключение не выбрасывается)
    - `test_invoke_with_tools_handles_tool_execution_error_gracefully` (заскриптованный `tool_calls` на существующий инструмент, вызов которого бросает исключение — `ToolMessage` с текстом ошибки ушёл во второй `ainvoke`, исключение наружу не просочилось)
    - `test_invoke_with_tools_does_not_mutate_input_messages_list` (после вызова с tool-calling сценарием исходный список `messages`, переданный в `invoke_with_tools`, не изменился — та же `len`/содержимое, что и до вызова)
  - `tests/modules/dialog/test_dialog_service.py` — добавить `test_send_message_uses_tool_result_in_final_reply`: `FakeChatModel(responses=[...])` с `tool_calls=[{"name": "get_current_time", ...}]` на первом шаге — проверить, что в БД сохранился именно финальный (второй) ответ ассистента, а не промежуточный.
  - Юнит-тест самого инструмента (без LLM): `tests/modules/dialog/test_tools.py` — `get_current_time` с валидным и невалидным `timezone`.
  - Зависит от Task 4.

### Phase 3: Документация, проверка

- [x] **Task 6: Документация (обязательный чекпоинт)**
  - Через `/aif-docs`: описать паттерн tool calling (`invoke_with_tools`, как добавлять новый инструмент, пример `get_current_time`, ограничение на один раунд без рекурсии). Уточнить у пользователя на чекпоинте — отдельная страница (например, `docs/tool-calling.md`) или раздел в `docs/dialog-chat.md`.
  - Обновить `AGENTS.md` (структура, точки входа) при необходимости.
  - Зависит от Task 1-5.

- [x] **Task 7: Финальная проверка**
  - Полный прогон тестов в Docker: `docker compose up -d postgres`, `docker compose run --rm app uv run pytest`.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Ручная сквозная проверка: как и в прошлом плане, без реального `OPENAI_API_KEY` возможна только smoke-проверка через `TestClient`/скрипт с фейковым ключом (конструктор `ChatOpenAI` не проверяет вызов инструментов без сети) — реальный tool-calling запрос к OpenAI не проверяется, если пользователь не даст ключ.
  - `docker compose down`, убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-6.
