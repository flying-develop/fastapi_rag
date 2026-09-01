"""Tests for `invoke_with_tools()` — no real LLM/network calls, uses
`FakeChatModel` (see `tests/modules/dialog/conftest.py`; imported
directly here since this helper is infra-level, not dialog-specific)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.infrastructure.llm import invoke_with_tools
from tests.modules.dialog.conftest import FakeChatModel


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def always_fails() -> str:
    """A tool that always raises — for testing graceful error handling."""
    raise RuntimeError("boom")


async def test_invoke_with_tools_returns_first_response_when_no_tool_calls() -> None:
    fake = FakeChatModel(reply="Plain answer")

    response = await invoke_with_tools(fake, [add], [])

    assert response.content == "Plain answer"
    assert len(fake.calls) == 1


async def test_invoke_with_tools_executes_tool_and_returns_final_response() -> None:
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "add", "args": {"a": 2, "b": 3}, "id": "call_1"}],
            ),
            AIMessage(content="The sum is 5."),
        ]
    )

    response = await invoke_with_tools(fake, [add], [])

    assert response.content == "The sum is 5."
    assert len(fake.calls) == 2
    tool_messages = [m for m in fake.calls[1] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "5"
    assert tool_messages[0].tool_call_id == "call_1"


async def test_invoke_with_tools_handles_unknown_tool_gracefully() -> None:
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "nonexistent", "args": {}, "id": "call_1"}],
            ),
            AIMessage(content="Final answer"),
        ]
    )

    response = await invoke_with_tools(fake, [add], [])

    assert response.content == "Final answer"
    tool_messages = [m for m in fake.calls[1] if isinstance(m, ToolMessage)]
    assert "unknown tool 'nonexistent'" in tool_messages[0].content


async def test_invoke_with_tools_handles_tool_execution_error_gracefully() -> None:
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "always_fails", "args": {}, "id": "call_1"}],
            ),
            AIMessage(content="Final answer"),
        ]
    )

    response = await invoke_with_tools(fake, [always_fails], [])

    assert response.content == "Final answer"
    tool_messages = [m for m in fake.calls[1] if isinstance(m, ToolMessage)]
    assert "failed" in tool_messages[0].content


async def test_invoke_with_tools_does_not_mutate_input_messages_list() -> None:
    fake = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "add", "args": {"a": 1, "b": 1}, "id": "call_1"}],
            ),
            AIMessage(content="Final"),
        ]
    )
    original = [HumanMessage(content="hi")]
    messages = list(original)

    await invoke_with_tools(fake, [add], messages)

    assert messages == original
