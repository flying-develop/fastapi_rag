"""LangGraph graph wrapping the dialog's LLM turn.

Second plan of the "Диалог как граф LangGraph" milestone: the previous
single-node graph (`agent` calling `invoke_with_tools()`, one round of tool
calling) is replaced by two nodes — `agent`/`tools` — connected by a
conditional edge, so the model can call tools across multiple rounds until
it produces a final answer.
"""

import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.llm import execute_tool_calls

logger = logging.getLogger(__name__)


class DialogState(TypedDict):
    """Graph state: the accumulated dialog message history.

    `add_messages` is LangGraph's standard reducer — each node returns the
    messages it wants appended, and the graph merges them into `messages`
    rather than the caller having to build the extended list by hand.
    """

    messages: Annotated[list[BaseMessage], add_messages]


def build_dialog_graph(
    chat_model: BaseChatModel, tools: list[BaseTool]
) -> CompiledStateGraph:
    """Build and compile the dialog graph.

    Two nodes:

    - **`agent`** — calls the model (with `tools` bound once, at build
      time) and returns its response as-is, whether or not it requests
      tools.
    - **`tools`** — executes the tool calls in the last `agent` response
      via `execute_tool_calls()` (shared with `invoke_with_tools()`, same
      error-handling/logging behavior) and returns the resulting
      `ToolMessage`s.

    A conditional edge (`_should_continue`) routes `agent`'s output: if it
    has `tool_calls`, go to `tools`; otherwise go to `END`. `tools` always
    routes back to `agent`, so the model can keep calling tools across
    multiple rounds — no longer limited to one round the way
    `invoke_with_tools()` is (that helper stays as the single-round option
    for direct, non-graph callers).

    We deliberately hand-roll the `tools` node instead of using
    `langgraph.prebuilt.ToolNode`/`tools_condition`: our own error-message
    format (`"Error: unknown tool '<name>'"`, `"Error: tool '<name>'
    failed: ..."`) is already documented and tested via
    `execute_tool_calls()`/`invoke_with_tools()`, and the prebuilt node
    doesn't produce it.

    Note on loop depth: LangGraph caps a single `.ainvoke()` at
    `recursion_limit=25` steps by default and raises `GraphRecursionError`
    if the model keeps requesting tools past that — no special handling is
    added here, it's caught by the existing `try/except Exception` in
    `DialogService.send_message` (ERROR log, re-raised).
    """
    model_with_tools = chat_model.bind_tools(tools) if tools else chat_model

    async def _agent_node(state: DialogState) -> dict:
        logger.info(
            "dialog graph: agent node invoked",
            extra={"message_count": len(state["messages"])},
        )
        response = await model_with_tools.ainvoke(state["messages"])
        logger.info(
            "dialog graph: agent node responded",
            extra={"response_length": len(str(response.content))},
        )
        return {"messages": [response]}

    async def _tools_node(state: DialogState) -> dict:
        last_message = state["messages"][-1]
        logger.info(
            "dialog graph: tools node invoked",
            extra={"tool_call_count": len(last_message.tool_calls)},
        )
        tool_messages = await execute_tool_calls(tools, last_message.tool_calls)
        logger.info(
            "dialog graph: tools node responded",
            extra={"tool_call_count": len(tool_messages)},
        )
        return {"messages": tool_messages}

    def _should_continue(state: DialogState) -> Literal["tools", "__end__"]:
        return "tools" if state["messages"][-1].tool_calls else END

    graph = StateGraph(DialogState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", _tools_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    logger.debug("dialog graph compiled")
    return graph.compile()
