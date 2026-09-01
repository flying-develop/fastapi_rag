"""LangChain chat model client, initialized from application `Settings`."""

import logging
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_chat_model() -> BaseChatModel:
    """Return a cached chat model client.

    Typed as the provider-neutral `BaseChatModel` rather than `ChatOpenAI`
    so callers (e.g. `DialogService`) don't depend on the concrete
    provider — switching to Gemini/Qwen later shouldn't require changing
    calling code (see `.ai-factory/DESCRIPTION.md`).
    """
    settings = get_settings()
    logger.debug("chat model client created", extra={"model": settings.openai_chat_model})
    return ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key)


async def invoke_with_tools(
    chat_model: BaseChatModel, tools: list[BaseTool], messages: list[BaseMessage]
) -> AIMessage:
    """Invoke `chat_model` with `tools` bound, executing any tool calls the
    model makes and returning its final reply.

    Reusable pattern: any module can call this with its own tool list —
    it doesn't have to be `dialog`-specific. Supports exactly one round of
    tool calling (model asks for tools once, gets results, replies) — no
    recursion / multi-step agentic loop; that's the "Диалог как граф
    LangGraph" milestone's job. Does not mutate the `messages` list passed
    in — callers may hold onto their own reference to it.
    """
    model_with_tools = chat_model.bind_tools(tools) if tools else chat_model
    response = await model_with_tools.ainvoke(messages)
    if not response.tool_calls:
        return response

    tools_by_name = {t.name: t for t in tools}
    extended = [*messages, response]
    for call in response.tool_calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            logger.warning("unknown tool requested", extra={"tool_name": call["name"]})
            result = f"Error: unknown tool '{call['name']}'"
        else:
            try:
                result = await tool.ainvoke(call["args"])
            except Exception as exc:
                logger.warning(
                    "tool execution failed",
                    extra={"tool_name": call["name"], "error_type": type(exc).__name__},
                )
                result = f"Error: tool '{call['name']}' failed: {exc}"
            else:
                logger.info(
                    "tool executed",
                    extra={"tool_name": call["name"], "tool_call_id": call["id"]},
                )
        extended.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    final = await model_with_tools.ainvoke(extended)
    if final.tool_calls:
        logger.warning(
            "tool calls in final response — nested tool calling not supported",
            extra={"tool_names": [c["name"] for c in final.tool_calls]},
        )
    return final
