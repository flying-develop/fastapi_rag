"""Example tool for the `dialog` module — demonstrates the tool-calling
pattern from `app.infrastructure.llm.invoke_with_tools` on a simple,
self-contained case (no new external dependencies)."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, tool


@tool
def get_current_time(timezone: str = "UTC") -> str:
    """Return the current date and time in the given IANA timezone
    (e.g. "UTC", "Europe/Moscow"). Defaults to UTC if not specified."""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return f"Error: unknown timezone '{timezone}'"
    return datetime.now(tz).isoformat()


DIALOG_TOOLS: list[BaseTool] = [get_current_time]
