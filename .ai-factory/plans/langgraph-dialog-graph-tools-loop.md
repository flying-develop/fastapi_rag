# LangGraph: узлы agent/tools с условными рёбрами

Branch: none
Created: 2026-09-06

## Original Request

full — второй и последний план вехи «Диалог как граф LangGraph»: разложить единственный узел `agent` (из app/modules/dialog/services/graph.py) на два узла `agent`/`tools` с условным переходом (если в ответе модели tool_calls — идти в tools, иначе в END), реализовать многошаговый tool calling через граф вместо однораундового ограничения invoke_with_tools(). Закрывает веху.

## Settings

- Testing: yes — тесты многошагового tool calling через граф (2+ раунда) плюс регрессия существующих тестов `graph`/`DialogService`/`invoke_with_tools`
- Logging: standard — INFO на вход/выход из узлов `agent` и `tools` (без содержимого сообщений целиком), тот же уровень детализации, что уже есть в `graph.py`/`llm.py`
- Docs: yes — обязательный чекпоинт документации по завершении

## Roadmap Linkage

Milestone: "Диалог как граф LangGraph"

Rationale: второй и последний план вехи. Первый план ввёл структуру графа с одним узлом `agent`, эквивалентным прежнему прямому вызову `invoke_with_tools()` (один раунд tool calling). Этот план заменяет тело `agent` на пару узлов `agent`/`tools` с условным переходом, снимая ограничение в один раунд и завершая веху.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-2): общий хелпер выполнения инструментов + узлы agent/tools с условным рёбром в графе.
   `feat(dialog): split dialog graph agent node into agent/tools with conditional routing`
2. **Checkpoint 2** (Tasks 3-4): подтверждение wiring в DialogService + тесты.
   `test(dialog): cover multi-round tool calling through the dialog graph`
3. **Checkpoint 3** (Tasks 5-6): документация, финальная проверка.
   `docs(dialog): document agent/tools graph loop; close LangGraph dialog milestone`

## Tasks

### Phase 1: Общий хелпер + узлы графа

- [x] **Task 1: Выделить `execute_tool_calls()` в `app/infrastructure/llm.py`**
  - Вынести из `invoke_with_tools()` цикл выполнения `tool_calls` в отдельную функцию:
    ```python
    async def execute_tool_calls(
        tools: list[BaseTool], tool_calls: list[dict]
    ) -> list[ToolMessage]
    ```
    — та же логика, что сейчас инлайн в `invoke_with_tools`: неизвестное имя инструмента → `ToolMessage(content="Error: unknown tool '<name>'")` + `WARN`; исключение при вызове → `ToolMessage(content="Error: tool '<name>' failed: <exc>")` + `WARN`; успех → `INFO` (`tool_name`, `tool_call_id`). Возвращает список `ToolMessage` в том же порядке, что и `tool_calls` (не мутирует ничего снаружи).
  - `invoke_with_tools()` переписать на использование `execute_tool_calls()` вместо инлайн-цикла — **чисто рефакторинг**, поведение и публичная сигнатура `invoke_with_tools()` не меняются; существующие тесты `tests/infrastructure/test_llm.py` должны пройти без изменений в утверждениях.
  - Причина: `execute_tool_calls()` нужен и `invoke_with_tools()` (однораундовый хелпер, остаётся для прямых вызовов вне графа), и новому узлу `tools` в графе (Task 2) — без дублирования логики обработки ошибок.
  - Логирование: без изменений уровня — тот же `WARN`/`INFO`, что уже был инлайн, просто перенесён в новую функцию.

- [x] **Task 2: Узлы `agent`/`tools` с условным рёбром — `app/modules/dialog/services/graph.py`**
  - Переписать `build_dialog_graph()`:
    - **`agent`**: `model_with_tools = chat_model.bind_tools(tools) if tools else chat_model` (привязка один раз при построении графа, не на каждый вызов узла — см. ниже), затем `response = await model_with_tools.ainvoke(state["messages"])`, возвращает `{"messages": [response]}`. Узел больше не вызывает `invoke_with_tools()` — цикл tool calling теперь на уровне графа (условное рёбро + узел `tools`), а не внутри одной функции.
    - **`tools`**: берёт `state["messages"][-1]` (последний `AIMessage`, всегда с непустым `tool_calls` — иначе граф направил бы в `END`, см. условное рёбро), вызывает `tool_messages = await execute_tool_calls(tools, last_message.tool_calls)`, возвращает `{"messages": tool_messages}`.
    - **Условное рёбро** `_should_continue(state) -> Literal["tools", "__end__"]`: `return "tools" if state["messages"][-1].tool_calls else END`.
    - Рёбра: `START → agent`; `agent` → условно `{"tools": "tools", END: END}` через `add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})`; `tools → agent` (обратно в agent — цикл продолжается, пока модель запрашивает инструменты).
  - Осознанное решение (задокументировать в docstring и в docs/dialog-graph.md): не использовать `langgraph.prebuilt.ToolNode`/`tools_condition` — свой узел `tools` через `execute_tool_calls()` сохраняет уже задокументированный и протестированный формат сообщений об ошибках (`"Error: unknown tool '<name>'"` и т.п.), которого нет в стандартном `ToolNode`.
  - Ограничение по глубине цикла: LangGraph по умолчанию ограничивает граф `recursion_limit=25` шагами и поднимает `GraphRecursionError` при превышении — специальной обработки не добавляется, штатно перехватывается существующим `try/except Exception` в `DialogService.send_message` (ERROR-лог, проброс дальше). Задокументировать это поведение, отдельно не тестировать (не часть текущего скоупа).
  - Логирование: INFO на вход/выход `agent` (как сейчас — `message_count` на входе, `response_length` на выходе) и на вход/выход `tools` (`tool_call_count` на входе, `tool_call_count` результатов на выходе) — тот же уровень детализации.
  - Импорт `Literal` из `typing`; `execute_tool_calls` из `app.infrastructure.llm`.
  - Зависит от Task 1.

### Phase 2: Wiring и тесты

- [x] **Task 3: Подтвердить wiring в `DialogService` — без изменений**
  - `app/modules/dialog/services/dialog_service.py`: публичная форма вызова графа не меняется — `self._graph.ainvoke({"messages": langchain_messages})` / `result["messages"][-1]`. Убедиться, что код действительно не требует правок (граф остаётся `CompiledStateGraph` с тем же контрактом состояния `DialogState`).
  - Прогнать существующие тесты `tests/modules/dialog/test_dialog_service.py` без изменений в утверждениях — поведенческий паритет (включая `test_send_message_uses_tool_result_in_final_reply`, который теперь проходит через полноценный agent/tools цикл вместо `invoke_with_tools()`, но с тем же наблюдаемым результатом).
  - Зависит от Task 2.

- [x] **Task 4: Тесты многошагового tool calling**
  - `tests/modules/dialog/test_graph.py`:
    - `test_graph_returns_final_response_when_no_tool_calls` — оставить как есть (граф сразу идёт в `END`, без захода в `tools`).
    - Переименовать/обновить `test_graph_executes_tool_and_returns_final_response` → один раунд tool calling по-прежнему работает (agent → tools → agent → END).
    - Новый `test_graph_executes_multiple_tool_call_rounds` — заскриптованные `responses` на 2 раунда (первый `AIMessage` с `tool_calls` на один инструмент, второй `AIMessage` тоже с `tool_calls` на другой/тот же инструмент, третий — финальный текст без `tool_calls`); проверить, что `result["messages"][-1]` — именно финальный текст, а `fake_chat_model.calls` показывает 3 вызова модели (то, что раньше было невозможно из-за ограничения `invoke_with_tools` в один раунд).
    - Обновить `test_graph_state_accumulates_input_messages`, чтобы явно проверить накопление и `ToolMessage`, а не только текстовых сообщений (можно расширить существующий тест или добавить отдельный `test_graph_state_includes_tool_messages`).
  - `tests/infrastructure/test_llm.py`: добавить прямой юнит-тест на новую `execute_tool_calls()` (неизвестный инструмент, исключение при вызове, успех) — сейчас это поведение проверяется только косвенно через `invoke_with_tools`; убедиться, что существующие тесты `invoke_with_tools()` проходят без изменений в утверждениях (регрессия после рефакторинга Task 1).
  - `tests/modules/dialog/conftest.py`: `FakeChatModel` уже поддерживает произвольную длину `responses=[...]` — изменений не требуется, только использование в новых тестах.
  - Зависит от Task 3.

### Phase 3: Документация, проверка

- [x] **Task 5: Документация (обязательный чекпоинт)**
  - `docs/dialog-graph.md`: переписать разделы про единственный узел — описать `agent`/`tools`, условное рёбро `_should_continue`, цикл `agent ⇄ tools` до тех пор, пока модель запрашивает инструменты, ограничение `recursion_limit` LangGraph по умолчанию (25 шагов) и как оно проявляется (`GraphRecursionError` → существующий `try/except` в `DialogService`). Явно отметить, что веха закрыта этим планом.
  - `docs/tool-calling.md`: обновить раздел про `invoke_with_tools()` — вынесенный `execute_tool_calls()` теперь используется и им, и узлом `tools` графа; убрать/скорректировать параграф "Ограничение" — многошаговый tool calling для диалога больше не ограничен одним раундом (решается на уровне графа), при этом `invoke_with_tools()` как отдельный хелпер для прямых (не графовых) вызовов сохраняет прежнее однораундовое поведение.
  - `AGENTS.md`: обновить краткое описание `graph.py` в таблице точек входа (agent/tools вместо одного узла), если формулировка устарела.
  - Через `/aif-docs`.
  - Зависит от Task 1-4.

- [x] **Task 6: Финальная проверка**
  - Пересобрать образ перед прогоном тестов: `docker compose build app` (обязательно после **любого** изменённого/нового файла — не только `uv add`, см. `.ai-factory/journal/langgraph-dialog-graph.md`).
  - `docker compose up -d postgres`, `docker compose run --rm app uv run pytest` — полный прогон, включая новые и существующие тесты.
  - Проверить компиляцию/импорт изменённых модулей, отсутствие TODO/debug-маркеров.
  - Ручная сквозная проверка: `docker compose up -d --build`, `curl /health` → `200 OK` (без реального `OPENAI_API_KEY` — только smoke, как в прошлых планах).
  - `docker compose down`, убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-5.
