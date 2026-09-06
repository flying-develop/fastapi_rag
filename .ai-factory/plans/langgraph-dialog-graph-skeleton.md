# LangGraph: базовый скелет графа диалога

Branch: none
Created: 2026-09-06

## Original Request

full — новая веха «Диалог как граф LangGraph»: перевод логики диалога (DialogService.send_message) на LangGraph — узлы/рёбра, состояние разговора, вызов инструментов из графа — вместо линейного invoke_with_tools. Первое знакомство с LangGraph в проекте. По стандартной практике пользователя разбить веху на несколько последовательных планов, а не один большой.

## Settings

- Testing: yes — тесты на графе напрямую (`FakeChatModel`, без реальных вызовов OpenAI) плюс регрессия существующих тестов `DialogService`
- Logging: standard — INFO на вход/выход из узла графа (без содержимого сообщений целиком)
- Docs: yes — обязательный чекпоинт документации по завершении (`/aif-docs`)

## Roadmap Linkage

Milestone: "Диалог как граф LangGraph"

Rationale: первый из двух планов вехи. Вводит саму структуру LangGraph — `StateGraph` с состоянием диалога (список сообщений) и одним узлом `agent`, компилируемым графом, вызываемым из `DialogService.send_message` вместо прямого вызова `invoke_with_tools()`. Поведение (включая один раунд tool calling) сохраняется без изменений — это инфраструктурный шаг знакомства с LangGraph. Второй план вехи разложит узел `agent` на полноценные `agent`/`tools` узлы с условными рёбрами для многошагового tool calling, закрывая веху.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-3): зависимость + состояние графа + узел `agent`.
   `feat(dialog): add langgraph dependency and build single-node dialog graph`
2. **Checkpoint 2** (Tasks 4-5): wiring в `DialogService` + тесты.
   `feat(dialog): wire dialog graph into DialogService.send_message; test: graph coverage`
3. **Checkpoint 3** (Task 6): документация, финальная проверка.
   `docs(dialog): document langgraph dialog graph skeleton`

## Tasks

### Phase 1: Зависимость и состояние графа

- [x] **Task 1: Добавить зависимость `langgraph`**
  - На хосте (не через `docker compose run` — см. `.ai-factory/journal/tool-calling.md`, изменения `pyproject.toml`/`uv.lock` теряются при удалении контейнера): `uv add langgraph`.
  - Пересобрать образ (`docker compose build app`), чтобы новая зависимость попала в контейнер.
  - Логирование не требуется (нет кода).

- [x] **Task 2: Состояние и построение графа — `app/modules/dialog/services/graph.py`**
  - `DialogState` — `TypedDict` с полем `messages: Annotated[list[BaseMessage], add_messages]` (редьюсер `langgraph.graph.message.add_messages` — стандартный паттерн LangGraph для накопления истории сообщений в состоянии).
  - `build_dialog_graph(chat_model: BaseChatModel, tools: list[BaseTool]) -> CompiledStateGraph`:
    - Один узел `"agent"`: `async def _agent_node(state: DialogState) -> dict` — вызывает `await invoke_with_tools(chat_model, tools, state["messages"])` (переиспользуем уже существующий хелпер из `app/infrastructure/llm.py` без изменений — в этом плане меняется только оболочка вызова, не сама логика tool calling) и возвращает `{"messages": [response]}`.
    - `StateGraph(DialogState)` → `add_node("agent", _agent_node)` → `add_edge(START, "agent")` → `add_edge("agent", END)` → `.compile()`.
    - Логирование: DEBUG при построении графа (без параметров, разово), INFO на вход в `_agent_node` (только количество сообщений в состоянии) и на выход (длина финального ответа) — тот же уровень детализации, что уже был в `DialogService.send_message` для вызова модели.
  - Импорты: `StateGraph`, `START`, `END`, `add_messages` из `langgraph.graph` (`add_messages` из `langgraph.graph.message`); `TypedDict`/`Annotated` из `typing`.
  - Зависит от Task 1.

### Phase 2: Wiring и тесты

- [x] **Task 3: Wiring в `DialogService`**
  - `app/modules/dialog/services/dialog_service.py`: в `__init__` построить и сохранить скомпилированный граф один раз — `self._graph = build_dialog_graph(chat_model, DIALOG_TOOLS)` (аналогично тому, как сейчас сохраняется `self._chat_model`; граф компилируется при создании сервиса, не на каждый вызов `send_message`).
  - В `send_message`: заменить `await invoke_with_tools(self._chat_model, DIALOG_TOOLS, langchain_messages)` на `result = await self._graph.ainvoke({"messages": langchain_messages})`, затем взять финальный ответ как `result["messages"][-1]` (последнее сообщение в накопленном состоянии — ответ узла `agent`).
  - Существующий `try/except Exception` вокруг вызова (ERROR-лог, проброс дальше) должен оборачивать вызов `self._graph.ainvoke(...)`, а не сырой `invoke_with_tools`.
  - Импорт `build_dialog_graph` из `app.modules.dialog.services.graph`; импорт `invoke_with_tools` из `dialog_service.py` можно убрать, если он там больше не используется напрямую.
  - Зависит от Task 2.

- [x] **Task 4: Тесты графа**
  - `tests/modules/dialog/test_graph.py` (новый) — тесты `build_dialog_graph()` напрямую с `FakeChatModel`:
    - `test_graph_returns_final_response_when_no_tool_calls` (0 tool calls → одно сообщение от `agent`, совпадает с ответом фейковой модели).
    - `test_graph_executes_tool_and_returns_final_response` (заскриптованные 2 ответа: первый с `tool_calls` на `get_current_time`, второй — финальный текст; проверить, что `result["messages"][-1]` — именно финальный ответ, а не промежуточный `AIMessage` с `tool_calls`).
    - `test_graph_state_accumulates_input_messages` (после `ainvoke` в `result["messages"]` присутствуют все входные сообщения плюс ответ(ы) узла — проверка редьюсера `add_messages`).
  - `tests/modules/dialog/test_dialog_service.py` — существующие тесты (`test_send_message_uses_tool_result_in_final_reply` и остальные) должны пройти без изменений в утверждениях (behavior parity) — при необходимости адаптировать только способ мока (`FakeChatModel` уже поддерживает `bind_tools`/`responses`, изменений не требуется).
  - Зависит от Task 3.

### Phase 3: Документация, проверка

- [x] **Task 5: Документация (обязательный чекпоинт)**
  - Через `/aif-docs`: новая страница (уточнить у пользователя на чекпоинте: отдельная `docs/dialog-graph.md` или раздел в `docs/dialog-chat.md`) — описать `DialogState`, узел `agent`, почему сейчас один узел (переходный шаг перед вторым планом вехи с `agent`/`tools` узлами и условными рёбрами), что поведение (включая один раунд tool calling через `invoke_with_tools` внутри узла) не изменилось.
  - Обновить перекрёстные ссылки: `docs/tool-calling.md`, `docs/dialog-chat.md`, `README.md`, `AGENTS.md` (дерево структуры — новый файл `graph.py`, `test_graph.py`; таблица документации).
  - Зависит от Task 1-4.

- [x] **Task 6: Финальная проверка**
  - Полный прогон тестов в Docker: `docker compose up -d postgres`, `docker compose run --rm app uv run pytest`.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Ручная сквозная проверка: без реального `OPENAI_API_KEY` — как и в прошлых планах, только smoke (`docker compose up -d --build`, `curl /health`); реальный запрос к OpenAI через граф не проверяется, если пользователь не даст ключ.
  - `docker compose down`, убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-5.
