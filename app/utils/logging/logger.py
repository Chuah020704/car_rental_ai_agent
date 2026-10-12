"""The only way the rest of the app should obtain a logger.

Usage: `logger = get_logger(__name__)` at module scope, then
`logger.info("event_name", key=value, ...)` — structlog treats the first
positional arg as the event name and everything else as structured fields.
"""

import structlog

from app.utils.logging.config import configure_logging


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog-bound logger, configuring logging on first call."""
    configure_logging()
    return structlog.get_logger(name)
