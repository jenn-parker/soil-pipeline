"""Application logging and request context helpers."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_id_context: ContextVar[str | None] = ContextVar("actor_id", default=None)


class JsonFormatter(logging.Formatter):
    """Format log records as structured JSON for container log collectors."""

    _standard_fields = set(logging.LogRecord(None, 0, "", 0, "", (), None).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        actor_id = actor_id_context.get()
        if request_id:
            event["request_id"] = request_id
        if actor_id:
            event["actor_id"] = actor_id

        for key, value in record.__dict__.items():
            if key not in self._standard_fields and not key.startswith("_"):
                event[key] = value
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, default=str)


def configure_logging() -> None:
    """Configure a small JSON logger suitable for local and container output."""

    root_logger = logging.getLogger()
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)
