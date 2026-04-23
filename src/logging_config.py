"""Logging configuration: human-readable on TTY, JSON in CI/non-TTY."""

import json
import logging
import sys
from typing import Final

__all__ = ["JsonFormatter", "configure_logging"]

_HUMAN_FORMAT: Final[str] = "%(levelname)s: %(message)s"

# Standard LogRecord attributes -- everything else on a record is treated as
# extra structured context and emitted in the JSON payload.
_STANDARD_RECORD_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line.

    Includes the standard fields (timestamp, level, logger, message) plus any
    keyword arguments passed via ``logger.info(..., extra={...})``. Exception
    tracebacks, when present, are emitted as a single ``exception`` field.

    Security note: this formatter passes through every non-standard
    ``LogRecord`` attribute. Callers must not log secrets, API keys, or other
    sensitive values via ``extra={...}``. Redact at the call site.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger.

    Logs are written to stderr (keeping stdout clean for the dry-run digest
    and other programmatic output). Format is human-readable when stderr is a
    TTY (interactive use) and JSON objects otherwise (CI, redirected output,
    log aggregation). Idempotent: a second call replaces the existing handlers
    rather than stacking.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    handler = logging.StreamHandler(sys.stderr)
    if sys.stderr.isatty():
        handler.setFormatter(logging.Formatter(_HUMAN_FORMAT))
    else:
        handler.setFormatter(JsonFormatter())

    root.addHandler(handler)
    root.setLevel(level)
