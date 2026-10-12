"""Processors that run before every log line is rendered.

The redaction processor exists because structlog's event_dict is just a plain
dict — anything a developer passes as a keyword argument (e.g. logger.info(...,
jwt_token=token)) would otherwise be rendered verbatim into logs/stdout. This is
the single choke point that prevents that from ever shipping.
"""

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

_REDACT_KEYS = {"password", "api_key", "apikey", "token", "secret", "authorization", "jwt"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def redact_processor(
    _logger: Any,  # noqa: ANN401 - structlog's own Processor type is Any-typed
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """Mask likely-sensitive keys and scrub emails from string values."""
    for key, value in list(event_dict.items()):
        if any(sensitive in key.lower() for sensitive in _REDACT_KEYS):
            event_dict[key] = "***REDACTED***"
        elif isinstance(value, str):
            event_dict[key] = _EMAIL_RE.sub("***EMAIL***", value)
    return event_dict
