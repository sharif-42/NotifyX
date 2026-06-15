"""Logging configuration: stdlib logging with a custom JSON formatter.

In development, logs are rendered as plain text for readability.
In any other environment, logs are rendered as JSON for machine parsing.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.shared.constants import Environment

# Standard LogRecord attributes that we don't want to duplicate in the JSON
# payload's "extra" section. Any attribute on the record that isn't in this
# set was added via `extra={...}` on a log call.
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "asctime",
        "message",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """
        Emit one JSON object per log record.

        Shape: {"timestamp": ISO-8601 UTC, "level": ..., "logger": ..., "message": ...}
        Any keys passed via ``logger.info(..., extra={...})`` are merged at the
        top level. Tracebacks are included under the ``exc_info`` key when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


# Per-logger overrides for noisy third-party libraries. Set these to WARNING
# unless you specifically want their INFO chatter in dev.
_THIRD_PARTY_LOG_LEVELS: dict[str, str] = {
    "sqlalchemy.engine": "WARNING",
    "httpx": "WARNING",
    "httpcore": "WARNING",
    "asyncpg": "WARNING",
    "arq": "INFO",
    "uvicorn": "INFO",
    "uvicorn.error": "INFO",
    "uvicorn.access": "INFO",
}


def configure_logging(level: str, environment: Environment) -> None:
    """Configure the root logger and per-library overrides.

    Call once at application startup (before any other code logs anything).
    Safe to call multiple times — handlers on the root logger are replaced
    rather than appended, so we don't end up with duplicate output.
    """

    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if environment == Environment.DEVELOPMENT:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JsonFormatter())

    root.addHandler(handler)

    for logger_name, logger_level in _THIRD_PARTY_LOG_LEVELS.items():
        logging.getLogger(logger_name).setLevel(logger_level)
