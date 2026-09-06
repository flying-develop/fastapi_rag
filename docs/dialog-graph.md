[← Tool calling у LLM](tool-calling.md) · [Back to README](../README.md) · [Работа с файлами →](files.md)

# Диалог как граф LangGraph

Второй и последний план вехи «Диалог как граф LangGraph» — граф с
двумя узлами, `agent`/`tools`, и условным рёбром между ними, заменяющий
прежний ограниченный одним раундом [`invoke_with_tools()`](tool-calling.md).
Модель теперь может запрашивать инструменты несколько раз подряд, пока не
даст финальный ответ.

## `DialogState`

`app/modules/dialog/services/graph.py`:

```python
class DialogState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

Состояние графа — накопленная история сообщений диалога. `add_messages`
— стандартный редьюсер LangGraph: узел возвращает только те сообщения,
которые хочет добавить, а граф сам сливает их в `messages`.

## `build_dialog_graph()`

```python
def build_dialog_graph(
    chat_model: BaseChatModel, tools: list[BaseTool]
) -> CompiledStateGraph
```

Два узла:

- **`agent`** — вызывает модель (инструменты привязаны один раз, при
  построении графа: `chat_model.bind_tools(tools)`) и возвращает её ответ
  как есть — с `tool_calls` или без.
- **`tools`** — выполняет `tool_calls` из последнего ответа `agent` через
  `execute_tool_calls()` из [Tool calling у LLM](tool-calling.md) (тот же
  общий хелпер, что и `invoke_with_tools()`, — одинаковый формат ошибок и
  логирование) и возвращает результаты как `ToolMessage`.

Условное рёбро `_should_continue(state)` направляет вывод `agent`:
если в последнем сообщении есть `tool_calls` — в `tools`, иначе — в
`END`. Ребро `tools → agent` возвращает выполнение обратно в `agent`, так
что цикл `agent ⇄ tools` продолжается, пока модель запрашивает
инструменты:

```
START → agent → (tool_calls?) → tools → agent → ... → END
```

Это снимает ограничение `invoke_with_tools()` в один раунд — многошаговый
tool calling теперь работает на уровне графа, а не одной функции.

Компилируется один раз в `DialogService.__init__`
(`self._graph = build_dialog_graph(chat_model, DIALOG_TOOLS)`), не на
каждый вызов `send_message`.

### Почему свой узел `tools`, а не `ToolNode`

LangGraph поставляет готовые `langgraph.prebuilt.ToolNode`/`tools_condition`
для той же задачи, но собственный узел `tools` через `execute_tool_calls()`
сохраняет уже задокументированный и протестированный формат сообщений об
ошибках (`"Error: unknown tool '<name>'"`, `"Error: tool '<name>' failed:
..."`), которого нет в стандартной реализации — осознанный выбор в пользу
согласованности с остальным проектом.

### Ограничение глубины цикла

LangGraph по умолчанию ограничивает граф `recursion_limit=25` шагами и
поднимает `GraphRecursionError`, если модель продолжает запрашивать
инструменты сверх этого лимита. Специальной обработки для этого случая
нет — исключение перехватывается уже существующим `try/except Exception`
в `DialogService.send_message` (ERROR-лог, проброс дальше), как и любая
другая ошибка вызова графа.

## Wiring в `DialogService`

`app/modules/dialog/services/dialog_service.py::send_message`:

```python
result = await self._graph.ainvoke({"messages": langchain_messages})
response = result["messages"][-1]
```

Публичная форма вызова не изменилась по сравнению с первым планом вехи —
переход на agent/tools узлы с условным рёбром никак не затронул
`DialogService`. `result["messages"][-1]` — последнее сообщение в
накопленном состоянии, т.е. финальный текстовый ответ `agent` (граф не
может завершиться на сообщении с `tool_calls` — тогда он направляется в
`tools`, а не в `END`). Промежуточные `AIMessage`/`ToolMessage` из цикла
tool calling по-прежнему не сохраняются в `dialog_messages`, как и раньше.

## Тесты

`tests/modules/dialog/test_graph.py` — `build_dialog_graph()` напрямую с
`FakeChatModel` (без БД, без реальных вызовов OpenAI):

- без `tool_calls` — граф сразу идёт в `END`, ответ модели как есть;
- один раунд tool calling — `agent → tools → agent → END`;
- несколько раундов подряд (`agent → tools → agent → tools → agent → END`)
  — то, что было невозможно при прежнем ограничении `invoke_with_tools()`
  в один раунд;
- состояние накапливает входные сообщения, `ToolMessage` из `tools` и
  финальный ответ (проверка редьюсера `add_messages`).

`tests/infrastructure/test_llm.py` — прямые юнит-тесты `execute_tool_calls()`
(успех, неизвестный инструмент, исключение при вызове, порядок результатов)
и регрессия `invoke_with_tools()` после рефакторинга (без изменений в
утверждениях).

Существующие тесты `tests/modules/dialog/test_dialog_service.py` проходят
без изменений в утверждениях — поведенческий паритет `send_message` не
нарушен.

## See Also

- [Диалоги с LLM](dialog-chat.md) — `DialogService`, эндпоинт `POST /dialogs/{id}/messages`
- [Tool calling у LLM](tool-calling.md) — `execute_tool_calls()`/`invoke_with_tools()`
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules
