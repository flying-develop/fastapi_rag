"""Structured (key=value) logging setup for the application."""

import logging
import sys

_RESERVED_LOG_RECORD_ATTRS = set(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__.keys()
)


class KeyValueFormatter(logging.Formatter):
    """Renders a log record as a single structured `key=value ...` line."""

    def format(self, record: logging.LogRecord) -> str:
        fields = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Extra fields passed via logger.debug(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                fields[key] = value

        line = " ".join(
            f'{key}="{value}"' if isinstance(value, str) else f"{key}={value}"
            for key, value in fields.items()
        )
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger with a structured stdout handler.

    Call exactly once at application startup, before any other logging.
    The level is fully controlled by `LOG_LEVEL` so it can be lowered in
    production without code changes.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    logging.getLogger(__name__).info(
        "logging initialized", extra={"log_level": log_level.upper()}
    )
