"""Tests for `build_dialog_graph()` — the `agent`/`tools` graph with
conditional routing — against `FakeChatModel` (no real OpenAI calls, no DB
needed)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.modules.dialog.services.graph import build_dialog_graph
from app.modules.dialog.services.tools import DIALOG_TOOLS
from tests.modules.dialog.conftest import FakeChatModel


async def test_graph_returns_final_response_when_no_tool_calls() -> None:
    fake_chat_model = FakeChatModel(reply="Hi there")
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hello")]})

    assert result["messages"][-1].content == "Hi there"
    assert len(fake_chat_model.calls) == 1


async def test_graph_executes_one_tool_round_and_returns_final_response() -> None:
    fake_chat_model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_current_time",
                        "args": {"timezone": "UTC"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="It is currently around noon UTC."),
        ]
    )
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="What time is it?")]}
    )

    assert result["messages"][-1].content == "It is currently around noon UTC."
    assert len(fake_chat_model.calls) == 2


async def test_graph_executes_multiple_tool_call_rounds() -> None:
    """The single-round limitation of `invoke_with_tools()` doesn't apply
    at the graph level — the model can request tools again after seeing
    the first round's results, and the graph keeps looping `agent` ->
    `tools` -> `agent` until a response without `tool_calls` arrives."""
    fake_chat_model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_current_time",
                        "args": {"timezone": "UTC"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_current_time",
                        "args": {"timezone": "Europe/Moscow"},
                        "id": "call_2",
                    }
                ],
            ),
            AIMessage(content="UTC and Moscow times reported above."),
        ]
    )
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="What time is it in UTC and Moscow?")]}
    )

    assert result["messages"][-1].content == "UTC and Moscow times reported above."
    assert len(fake_chat_model.calls) == 3


async def test_graph_state_accumulates_input_messages() -> None:
    fake_chat_model = FakeChatModel(reply="Hi there")
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    input_messages = [
        HumanMessage(content="Earlier question"),
        AIMessage(content="Earlier answer"),
        HumanMessage(content="Follow-up"),
    ]
    result = await graph.ainvoke({"messages": input_messages})

    assert [m.content for m in result["messages"]] == [
        "Earlier question",
        "Earlier answer",
        "Follow-up",
        "Hi there",
    ]


async def test_graph_state_includes_tool_messages() -> None:
    fake_chat_model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_current_time",
                        "args": {"timezone": "UTC"},
                        "id": "call_1",
                    }
                ],
            ),
            AIMessage(content="It is currently around noon UTC."),
        ]
    )
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="What time is it?")]}
    )

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_1"
