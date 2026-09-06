[← Диалоги с LLM](dialog-chat.md) · [Back to README](../README.md)

# Tool calling у LLM

Переиспользуемый паттерн для structured tool calling через LangChain:
модель не просто генерирует текст, а вызывает инструменты-функции,
параметры и результат которых описаны Pydantic-схемами. Первая веха,
где паттерн применяется — [Диалоги с LLM](dialog-chat.md)
(`DialogService`), но сам хелпер dialog-агностичный и рассчитан на
переиспользование в будущих вехах (RAG-поиск, БД-запросы, внешние API).

## `invoke_with_tools()`

`app/infrastructure/llm.py`:

```python
async def invoke_with_tools(
    chat_model: BaseChatModel, tools: list[BaseTool], messages: list[BaseMessage]
) -> AIMessage
```

Алгоритм:

1. Привязать инструменты к модели (`chat_model.bind_tools(tools)`), если список непустой.
2. Вызвать модель. Если в ответе нет `tool_calls` — вернуть ответ как есть (без изменений, один `ainvoke` — как до появления tool calling).
3. Иначе — выполнить каждый запрошенный `tool_call` через `execute_tool_calls()` (см. ниже), собрать результаты в **новый** список сообщений (исходный `messages`, переданный вызывающей стороной, не мутируется).
4. Вызвать модель повторно с учётом результатов инструментов — это финальный ответ.

## `execute_tool_calls()`

`app/infrastructure/llm.py`:

```python
async def execute_tool_calls(
    tools: list[BaseTool], tool_calls: list[dict]
) -> list[ToolMessage]
```

Выполняет список `tool_calls`, по одному `ToolMessage` на вызов, в
исходном порядке. Общий хелпер: используется и `invoke_with_tools()`
(ниже), и узлом `tools` [графа диалога](dialog-graph.md) — вынесен, чтобы
не дублировать обработку ошибок между однораундовым вызовом и
многораундовым циклом графа.

Обработка ошибок — без исключений наружу, инструмент сам "объясняет" модели, что пошло не так:

- Неизвестное имя инструмента → `ToolMessage(content="Error: unknown tool '<name>'")`, `WARN` в лог.
- Инструмент найден, но вызов упал (невалидные аргументы, ошибка выполнения) → `ToolMessage(content="Error: tool '<name>' failed: <exc>")`, `WARN` в лог.
- Успешный вызов → `INFO` в лог (`tool_name`, `tool_call_id`).

**Ограничение `invoke_with_tools()` (осознанное, задокументированное):** только один раунд tool calling — без рекурсии/многошаговых агентных циклов. Если финальный ответ модели сам содержит `tool_calls` (модель снова запросила инструмент), функция всё равно вернёт его как есть — но залогирует `WARN` ("tool calls in final response — nested tool calling not supported"), чтобы это не прошло незамеченным. Это ограничение относится только к прямым (не графовым) вызовам `invoke_with_tools()` — [граф диалога](dialog-graph.md) реализует полноценный многошаговый цикл через свои узлы `agent`/`tools` и тот же `execute_tool_calls()`, без ограничения в один раунд.

## Как добавить новый инструмент

1. Написать функцию с типизированной сигнатурой и docstring, задекорировать `@tool` из `langchain_core.tools` — LangChain сам сгенерирует Pydantic-схему параметров из аннотаций типов.
2. Функция может быть sync или async — `BaseTool.ainvoke()` одинаково работает в обоих случаях (sync выполняется в threadpool).
3. Внутри функции — graceful-ошибки текстом, а не исключения, где это осмысленно (по примеру `get_current_time`), но это не обязательное требование: `execute_tool_calls`/`invoke_with_tools` в любом случае перехватят исключение из `tool.ainvoke(...)`.
4. Собрать список инструментов модуля (например, `DIALOG_TOOLS`) и передать его в [граф диалога](dialog-graph.md) (`build_dialog_graph(chat_model, MY_TOOLS)`) для многошагового tool calling, либо в `invoke_with_tools(chat_model, MY_TOOLS, messages)` вместо прямого `chat_model.ainvoke(messages)`, если достаточно одного раунда.

## Пример: `get_current_time`

`app/modules/dialog/services/tools.py`:

```python
@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Return the current date and time in the given IANA timezone
    (e.g. "UTC", "Europe/Moscow"). Defaults to UTC if not specified."""
    ...
```

Единственный параметр — `timezone: str`, без новых зависимостей (`zoneinfo` — stdlib). Невалидный часовой пояс возвращает текстовую ошибку, не исключение.

`DIALOG_TOOLS` используется [графом диалога](dialog-graph.md), вызываемым
из `DialogService.send_message` — не напрямую через `invoke_with_tools()`
(тот остаётся отдельным однораундовым хелпером для прямых, не графовых
вызовов).

## Персистентность истории

Промежуточные сообщения tool-calling обмена (`AIMessage` с `tool_calls`,
`ToolMessage` с результатами) **не сохраняются** в `dialog_messages` —
осознанное упрощение для базового паттерна. В историю диалога попадает
только финальный текстовый ответ ассистента, как и до появления tool
calling. Полный обмен с инструментами живёт только в рамках одного
вызова `send_message`.

## Тесты

- `tests/infrastructure/test_llm.py` — `invoke_with_tools()` и `execute_tool_calls()` напрямую, с `FakeChatModel` (без реальных вызовов OpenAI). `FakeChatModel` живёт в `tests/modules/dialog/conftest.py`, но импортируется сюда напрямую (`from tests.modules.dialog.conftest import FakeChatModel`) — хелперы dialog-агностичные, а фейк пока единственный в проекте.
- `tests/modules/dialog/test_dialog_service.py::test_send_message_uses_tool_result_in_final_reply` — сквозной сценарий с `get_current_time` через `DialogService`.
- `tests/modules/dialog/test_tools.py` — юнит-тесты `get_current_time` (без LLM).

## See Also

- [Диалоги с LLM](dialog-chat.md) — `DialogService`, эндпоинт `POST /dialogs/{id}/messages`
- [Диалог как граф LangGraph](dialog-graph.md) — граф, узел `tools` которого использует `execute_tool_calls()`
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — структура модулей
