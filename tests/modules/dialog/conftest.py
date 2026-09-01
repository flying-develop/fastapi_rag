"""Fixtures for the `dialog` module tests."""

import pytest
from langchain_core.messages import AIMessage


class FakeChatModel:
    """Minimal stand-in for a LangChain chat model — no real network
    calls (no OpenAI key needed in tests). Implements only what
    `DialogService`/`invoke_with_tools` actually use (`ainvoke`,
    `bind_tools`), and records every message list it was called with so
    tests can assert on what was sent.

    Default behavior (no `responses` passed) is unchanged from before
    tool-calling support was added: a single `ainvoke` call always
    returns `AIMessage(content=self.reply)` with no `tool_calls` — the
    existing tests that only check `.reply`/`.calls[0]` keep working.

    Pass `responses=[...]` to script a sequence of `AIMessage` objects
    returned in order across calls (e.g. one with `tool_calls` set,
    followed by a final plain-text one) to simulate tool-calling.
    """

    def __init__(
        self, reply: str = "Fake reply", responses: list[AIMessage] | None = None
    ) -> None:
        self.reply = reply
        self._responses = list(responses) if responses is not None else None
        self.calls: list[list] = []
        self.bound_tools: list | None = None

    def bind_tools(self, tools: list) -> "FakeChatModel":
        self.bound_tools = list(tools)
        return self

    async def ainvoke(self, messages: list) -> AIMessage:
        self.calls.append(messages)
        if self._responses is not None:
            return self._responses.pop(0)
        return AIMessage(content=self.reply)


@pytest.fixture
def fake_chat_model() -> FakeChatModel:
    return FakeChatModel()
