"""Structured logging setup using structlog.

Features:
- JSON logs in all environments (dev pretty vs prod compact)
- Automatic request_id injection from RequestIDMiddleware
- Supports logging via stdlib logging OR structlog logger
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, MutableMapping
import structlog
from datetime import datetime, timezone

try:  # runtime import safety
    from app.middleware.request_id import get_request_id
except Exception:  # pragma: no cover
    def get_request_id():  # type: ignore
        return None


def _add_request_id(logger: Any, method: str, event_dict: MutableMapping[str, Any]):  # structlog processor
    rid = get_request_id()
    if rid:
        event_dict.setdefault("request_id", rid)
    else:
        event_dict.setdefault("request_id", "-")
    return event_dict


def _add_timestamp(logger: Any, method: str, event_dict: MutableMapping[str, Any]):
    event_dict["ts"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return event_dict


def _add_log_level(logger: Any, method: str, event_dict: MutableMapping[str, Any]):
    event_dict.setdefault("level", method.upper())
    return event_dict


def _rename_event_key(logger: Any, method: str, event_dict: MutableMapping[str, Any]):
    # structlog uses "event" by default; rename to message for consistency
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def setup_logging(env: str | None = None) -> None:
    env = (env or os.getenv("BB_ENV") or "dev").lower()
    is_dev = env != "prod"

    # Reset any existing configuration to avoid duplicate handlers in reload
    for h in list(logging.root.handlers):
        logging.root.removeHandler(h)

    shared_processors: list[structlog.types.Processor] = [
        _add_timestamp,
        _add_request_id,
        _add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _rename_event_key,
    ]

    if is_dev:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # merge contextvars (if used elsewhere)
            *shared_processors,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging -> structlog
    class _StructlogFormatter(logging.Formatter):  # minimal; structlog handles formatting
        def format(self, record: logging.LogRecord):  # type: ignore[override]
            logger = structlog.get_logger(record.name)
            # gather extras
            kwargs = {
                k: v
                for k, v in record.__dict__.items()
                if k not in {"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
                             "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated",
                             "thread", "threadName", "processName", "process", "message"}
            }
            if record.exc_info:
                kwargs["exc_info"] = record.exc_info
            # Use record.msg % record.args semantics
            msg = record.getMessage()
            logger.log(record.levelno, msg, **kwargs)
            return ""  # structlog already emitted the line

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_StructlogFormatter())
    root_level = "DEBUG" if is_dev else "INFO"
    logging.basicConfig(handlers=[handler], level=root_level, force=True)

    # Reduce noise from libraries in prod
    if not is_dev:
        for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):  # tune as needed
            logging.getLogger(noisy).setLevel(os.getenv("BB_LOG_LIB_LEVEL", "WARNING"))

    structlog.get_logger(__name__).info("logging_configured", env=env)


__all__ = ["setup_logging"]
