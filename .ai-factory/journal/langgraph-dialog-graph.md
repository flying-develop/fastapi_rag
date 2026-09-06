# Журнал реализации: Диалог как граф LangGraph

Веха roadmap: «Диалог как граф LangGraph»
Планы вехи:
- `.ai-factory/plans/langgraph-dialog-graph-skeleton.md` — базовый скелет графа (реализован, 6/6).
- `.ai-factory/plans/langgraph-dialog-graph-tools-loop.md` — узлы `agent`/`tools` с условным рёбром, многошаговый tool calling (реализован, 6/6). Закрывает веху.

## План 1: Базовый скелет графа

### Task 1 — Зависимость `langgraph`

- На хосте: `uv add langgraph` (не через `docker compose run` — та же причина, что и для `langchain`/`langchain-openai` в прошлой вехе: изменения `pyproject.toml`/`uv.lock` теряются при удалении одноразового контейнера). Добавлено `langgraph>=1.2.11` (тянет `langgraph-checkpoint`, `langgraph-prebuilt`, `langgraph-sdk`).
- `docker compose build app` — пересборка образа под новую зависимость.

### Task 2 — `DialogState` и `build_dialog_graph()`

- `app/modules/dialog/services/graph.py`: `DialogState` (`TypedDict`) с единственным полем `messages: Annotated[list[BaseMessage], add_messages]` — стандартный редьюсер LangGraph для накопления истории.
- `build_dialog_graph(chat_model, tools) -> CompiledStateGraph`: один узел `agent`, внутри которого вызывается уже существующий `invoke_with_tools()` из `app/infrastructure/llm.py` **без изменений** — в этом плане меняется только оболочка вызова (граф вместо прямого вызова), не сама логика tool calling. Граф: `START → agent → END`.
- Импорты подтверждены смоук-тестом в контейнере перед написанием кода: `from langgraph.graph import StateGraph, START, END`, `from langgraph.graph.message import add_messages`, `from langgraph.graph.state import CompiledStateGraph`.

### Task 3 — Wiring в `DialogService`

- `__init__`: граф строится один раз — `self._graph = build_dialog_graph(chat_model, DIALOG_TOOLS)` (не на каждый вызов `send_message`).
- `send_message`: `await invoke_with_tools(...)` заменён на `result = await self._graph.ainvoke({"messages": langchain_messages})`, финальный ответ — `result["messages"][-1]`. `try/except` вокруг вызова модели теперь оборачивает `self._graph.ainvoke(...)`.
- `self._chat_model` оставлено полем (используется только для построения графа в `__init__`, но сохранение ссылки осмысленно и не мешает).

### Task 4 — Тесты графа

- `tests/modules/dialog/test_graph.py` (новый) — 3 теста `build_dialog_graph()` напрямую с `FakeChatModel`, без БД: без tool calls, с tool call + финальным ответом, накопление сообщений в состоянии (`add_messages`).
- **Отловленный момент, не проблема**: после добавления нового тестового файла `docker compose run --rm app uv run pytest` без пересборки образа показал старые 30/30 (файл не попал в контейнер — тот же класс поведения, что уже документирован для миграций: `docker compose run` без bind-mount видит только код, запечённый в образ на момент сборки). Пересборка (`docker compose build app`) перед прогоном — обязательный шаг после любого нового файла, не только после `uv add`.
- Итог: 33/33 (30 старых + 3 новых) проходят без изменений в существующих тестах `test_dialog_service.py` — поведенческий паритет подтверждён.

### Task 5 — Документация (обязательный чекпоинт)

- Выбор пользователя: отдельная страница `docs/dialog-graph.md` (`DialogState`, узел `agent`, `build_dialog_graph()`, почему пока один узел, тесты).
- Обновлены перекрёстные ссылки и убрано устаревшее утверждение "LangGraph здесь не используется" из `docs/dialog-chat.md` (было актуально до этого плана); `docs/tool-calling.md`, `README.md`, `AGENTS.md` (дерево структуры — `graph.py`/`test_graph.py`, таблица точек входа, таблица документации).

### Task 6 — Сквозная проверка

- Компиляция/импорт `graph.py`/`dialog_service.py` — ok. TODO/FIXME-маркеров нет. `docker compose run --rm app uv run pytest` — 33/33 passed.
- `docker compose up -d --build` — полный стек healthy, `curl /health` → `200 OK`.
- `docker compose down` — root-owned файлов не осталось.

**Итог плана:** структура LangGraph введена в проект (состояние, узел, компиляция, вызов из сервиса) без изменения наблюдаемого поведения — переходный шаг перед вторым планом вехи, который разложит узел `agent` на `agent`/`tools` с условными рёбрами и снимет ограничение `invoke_with_tools()` в один раунд tool calling. Веха «Диалог как граф LangGraph» пока не закрыта — второй план ещё предстоит.

## План 2: Узлы agent/tools с условными рёбрами

### Task 1 — `execute_tool_calls()` в `app/infrastructure/llm.py`

- Цикл выполнения `tool_calls` (неизвестный инструмент → `WARN` + `ToolMessage` с ошибкой; исключение при вызове → `WARN` + `ToolMessage` с ошибкой; успех → `INFO`) вынесен из `invoke_with_tools()` в отдельную `execute_tool_calls(tools, tool_calls) -> list[ToolMessage]`.
- `invoke_with_tools()` переписан на использование `execute_tool_calls()` — чисто рефакторинг, публичная сигнатура и поведение не изменились (проверено регрессией `tests/infrastructure/test_llm.py`).
- Общий хелпер нужен, чтобы не дублировать обработку ошибок между `invoke_with_tools()` (однораундовый, для прямых вызовов) и новым узлом `tools` графа (Task 2).

### Task 2 — `agent`/`tools` узлы с условным рёбром — `app/modules/dialog/services/graph.py`

- `build_dialog_graph()` переписан: `agent` вызывает модель напрямую (`chat_model.bind_tools(tools)` один раз при построении графа) вместо `invoke_with_tools()`; новый узел `tools` вызывает `execute_tool_calls()` на `tool_calls` последнего сообщения.
- Условное рёбро `_should_continue`: `tool_calls` есть → `tools`, иначе → `END`. Ребро `tools → agent` замыкает цикл — модель может запрашивать инструменты несколько раз подряд.
- Осознанно не используется `langgraph.prebuilt.ToolNode`/`tools_condition` — свой узел сохраняет уже задокументированный формат сообщений об ошибках.
- Ограничение `recursion_limit=25` (default LangGraph) не обрабатывается отдельно — `GraphRecursionError` перехватывается существующим `try/except` в `DialogService.send_message`.

### Task 3 — `DialogService`: подтверждено, изменений не требуется

- Публичная форма вызова графа (`self._graph.ainvoke(...)` / `result["messages"][-1]`) не изменилась — переход на agent/tools узлы полностью инкапсулирован в `graph.py`. Хорошее свойство абстракции графа: вызывающий код не заметил изменения внутренней структуры.

### Task 4 — Тесты

- `tests/modules/dialog/test_graph.py`: добавлен `test_graph_executes_multiple_tool_call_rounds` (2 раунда tool calling подряд — то, что было невозможно при прежнем ограничении `invoke_with_tools()`), `test_graph_state_includes_tool_messages`; существующие тесты обновлены/переименованы, продолжают проходить.
- `tests/infrastructure/test_llm.py`: добавлены прямые юнит-тесты `execute_tool_calls()` (успех, неизвестный инструмент, ошибка выполнения, порядок результатов); регрессия `invoke_with_tools()` — без изменений в утверждениях.
- `tests/modules/dialog/test_dialog_service.py` — без изменений, поведенческий паритет подтверждён.

### Task 5 — Документация

- `docs/dialog-graph.md` переписан под новую структуру (agent/tools, условное рёбро, цикл, ограничение recursion_limit, обоснование отказа от `ToolNode`).
- `docs/tool-calling.md`: добавлен раздел `execute_tool_calls()`, скорректировано "Ограничение" (относится только к прямым вызовам `invoke_with_tools()`, не к графу), убран устаревший пример вызова `invoke_with_tools()` из `DialogService`.
- `AGENTS.md`: обновлены описания `graph.py`/`llm.py`/тестов в дереве структуры и таблице точек входа.

### Task 6 — Финальная проверка

- `docker compose build app` перед прогоном (обязательно после любых изменённых/новых файлов — см. План 1).
- `docker compose run --rm app uv run pytest` — полный прогон.
- `docker compose up -d --build` → `curl /health` → `200 OK`; `docker compose down` — без root-owned файлов.

**Итог плана:** веха «Диалог как граф LangGraph» закрыта — граф диалога теперь поддерживает полноценный многошаговый tool calling через цикл `agent ⇄ tools` с условным рёбром, вместо однораундового ограничения `invoke_with_tools()`.
