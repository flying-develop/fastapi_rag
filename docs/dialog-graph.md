[← Tool calling у LLM](tool-calling.md) · [Back to README](../README.md)

# Диалог как граф LangGraph

Первый план вехи «Диалог как граф LangGraph» — базовый скелет: сама
структура LangGraph (состояние, узел, граф), заменяющая прямой вызов
`invoke_with_tools()` из [`DialogService`](dialog-chat.md), без
изменения поведения. Второй план вехи разложит единственный узел
`agent` на полноценные `agent`/`tools` узлы с условными рёбрами для
многошагового tool calling — подробности будут здесь же после его
реализации.

## `DialogState`

`app/modules/dialog/services/graph.py`:

```python
class DialogState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

Состояние графа — накопленная история сообщений диалога. `add_messages`
— стандартный редьюсер LangGraph: узел возвращает только те сообщения,
которые хочет добавить, а граф сам сливает их в `messages`, не
заставляя вызывающий код вручную собирать расширенный список (как это
раньше делал `invoke_with_tools()` для собственного внутреннего цикла —
там это осталось без изменений).

## `build_dialog_graph()`

```python
def build_dialog_graph(
    chat_model: BaseChatModel, tools: list[BaseTool]
) -> CompiledStateGraph
```

Пока один узел:

- **`agent`** — вызывает `invoke_with_tools(chat_model, tools, state["messages"])`
  (существующий хелпер из [Tool calling у LLM](tool-calling.md), логика
  не изменилась — один раунд tool calling внутри узла) и возвращает
  `{"messages": [response]}`.

Граф: `START → agent → END`. Компилируется один раз в
`DialogService.__init__` (`self._graph = build_dialog_graph(chat_model, DIALOG_TOOLS)`),
не на каждый вызов `send_message`.

Функция спроектирована так же, как `invoke_with_tools()` — dialog-агностично
по сигнатуре (принимает `chat_model`/`tools` параметрами), хотя пока
используется только модулем `dialog`.

## Wiring в `DialogService`

`app/modules/dialog/services/dialog_service.py::send_message`:

```python
result = await self._graph.ainvoke({"messages": langchain_messages})
response = result["messages"][-1]
```

Вместо прямого `await invoke_with_tools(self._chat_model, DIALOG_TOOLS, langchain_messages)`.
`result["messages"][-1]` — последнее сообщение в накопленном состоянии,
т.е. ответ узла `agent`. Остальная логика (сохранение user-сообщения до
вызова, сохранение финального ответа ассистента после) не изменилась.

## Почему один узел

Это переходный шаг: ввести структуру графа (состояние, узел, компиляция,
вызов из сервиса) на самом простом случае — один узел, эквивалентный
прежнему прямому вызову — прежде чем усложнять граф условными рёбрами.
Второй план вехи заменит тело `agent` на пару узлов `agent`/`tools` с
условным переходом (`tools_condition`-подобная логика: если в ответе
модели есть `tool_calls` — идти в `tools`, иначе — в `END`), что снимет
текущее ограничение `invoke_with_tools()` в один раунд tool calling.

## Тесты

`tests/modules/dialog/test_graph.py` — `build_dialog_graph()` напрямую
с `FakeChatModel` (без БД, без реальных вызовов OpenAI):

- без `tool_calls` — граф возвращает ответ модели как есть;
- с `tool_calls` — граф выполняет инструмент и возвращает финальный
  (второй) ответ, а не промежуточный;
- состояние действительно накапливает входные сообщения плюс ответ
  узла (проверка редьюсера `add_messages`).

Существующие тесты `tests/modules/dialog/test_dialog_service.py`
проходят без изменений в утверждениях — поведение `send_message` не
поменялось.

## See Also

- [Диалоги с LLM](dialog-chat.md) — `DialogService`, эндпоинт `POST /dialogs/{id}/messages`
- [Tool calling у LLM](tool-calling.md) — `invoke_with_tools()`, вызываемый из узла `agent`
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules
