"""Wires structlog on top of stdlib logging.

Why structlog instead of plain stdlib logging: it gives us structured
(key=value / JSON) log events instead of hand-formatted strings, and
`structlog.contextvars` lets us bind a trace_id/customer_id once per request
and have it automatically attached to every log line emitted during that
request — no need to pass it through every function call manually.
"""

import logging
import sys

import structlog

from app.utils.config import get_settings
from app.utils.logging.formatter import redact_processor

_configured = False


def configure_logging() -> None:
    """Idempotent: safe to call multiple times, only wires handlers once."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_processor,
    ]

    # JSON in non-interactive environments (CI, Docker); human-readable locally.
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if sys.stderr.isatty()
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    _configured = True
