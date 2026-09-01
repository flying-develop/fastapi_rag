"""Unit tests for `dialog` module tools — no LLM involved."""

from app.modules.dialog.services.tools import get_current_time


def test_get_current_time_returns_iso_format_for_valid_timezone() -> None:
    result = get_current_time.invoke({"timezone": "Europe/Moscow"})
    assert "T" in result


def test_get_current_time_defaults_to_utc() -> None:
    result = get_current_time.invoke({})
    assert "T" in result


def test_get_current_time_returns_error_message_for_invalid_timezone() -> None:
    result = get_current_time.invoke({"timezone": "Not/AZone"})
    assert result == "Error: unknown timezone 'Not/AZone'"
