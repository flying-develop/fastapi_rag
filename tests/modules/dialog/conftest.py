"""Fixtures for the `dialog` module tests."""

import pytest
from langchain_core.messages import AIMessage


class FakeChatModel:
    """Minimal stand-in for a LangChain chat model — no real network
    calls (no OpenAI key needed in tests). Implements only what
    `DialogService` actually uses (`ainvoke`), and records every message
    list it was called with so tests can assert on what was sent."""

    def __init__(self, reply: str = "Fake reply") -> None:
        self.reply = reply
        self.calls: list[list] = []

    async def ainvoke(self, messages: list) -> AIMessage:
        self.calls.append(messages)
        return AIMessage(content=self.reply)


@pytest.fixture
def fake_chat_model() -> FakeChatModel:
    return FakeChatModel()
