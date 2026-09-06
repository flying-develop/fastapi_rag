"""Tests for `build_dialog_graph()` — the single-node LangGraph skeleton,
against `FakeChatModel` (no real OpenAI calls, no DB needed)."""

from langchain_core.messages import AIMessage, HumanMessage

from app.modules.dialog.services.graph import build_dialog_graph
from app.modules.dialog.services.tools import DIALOG_TOOLS
from tests.modules.dialog.conftest import FakeChatModel


async def test_graph_returns_final_response_when_no_tool_calls() -> None:
    fake_chat_model = FakeChatModel(reply="Hi there")
    graph = build_dialog_graph(fake_chat_model, DIALOG_TOOLS)

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hello")]})

    assert result["messages"][-1].content == "Hi there"


async def test_graph_executes_tool_and_returns_final_response() -> None:
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
