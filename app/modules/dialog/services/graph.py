"""LangGraph graph wrapping the dialog's LLM turn.

First LangGraph usage in the project — a deliberately minimal single-node
graph. It wraps the existing `invoke_with_tools()` one-round tool-calling
helper unchanged, so behavior is identical to the previous direct call;
this step only introduces the graph structure (state, node, edges) that
the next milestone plan will extend into a real `agent`/`tools` loop with
conditional routing.
"""

import logging
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.llm import invoke_with_tools

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
    """Build and compile the single-node dialog graph.

    One node (`agent`) delegates to `invoke_with_tools()` for the actual
    LLM call and tool-calling round — that logic is unchanged. Reusable
    the same way `invoke_with_tools()` is: callers just supply their own
    `chat_model`/`tools`.
    """

    async def _agent_node(state: DialogState) -> dict:
        logger.info("dialog graph: agent node invoked", extra={"message_count": len(state["messages"])})
        response = await invoke_with_tools(chat_model, tools, state["messages"])
        logger.info(
            "dialog graph: agent node responded",
            extra={"response_length": len(str(response.content))},
        )
        return {"messages": [response]}

    graph = StateGraph(DialogState)
    graph.add_node("agent", _agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)

    logger.debug("dialog graph compiled")
    return graph.compile()
