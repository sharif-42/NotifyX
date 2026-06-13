import json
import logging
import logging.config
from datetime import datetime, timezone

# Standard LogRecord attributes that we don't want to surface as top-level
# fields in the JSON output. Anything else on `record.__dict__` is treated
# as an `extra=` field passed by the caller (e.g. request_id, tenant_id).
_RESERVED_LOGRECORD_ATTRS: frozenset[str] = frozenset(
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


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Shape: {"ts": ISO-8601 UTC, "level": ..., "logger": ..., "message": ...}
    Any keys passed via ``logger.info(..., extra={...})`` are merged at the
    top level. Tracebacks are included under the ``exc_info`` key when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", json: bool = False) -> None:
    formatter_name = "json" if json else "standard"
    formatter_cfg: dict[str, str]
    if json:
        # The class is referenced by dotted path so dictConfig can locate it.
        formatter_cfg = {"()": "app.core.logging._JsonFormatter"}
    else:
        formatter_cfg = {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"}

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
                "json": formatter_cfg,
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "level": level.upper(),
                }
            },
            "root": {"handlers": ["default"], "level": level.upper()},
        }
    )

