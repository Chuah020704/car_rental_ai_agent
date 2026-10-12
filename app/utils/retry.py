"""Exponential-backoff retry for flaky I/O (LLM calls, tool calls, network requests)."""

import asyncio
from collections.abc import Awaitable, Callable

from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


async def retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "operation",
) -> T:
    """Call `fn` up to `max_attempts` times with exponential backoff between tries.

    Re-raises the last exception if every attempt fails.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # intentionally broad: any failure triggers a retry
            last_exc = exc
            logger.warning(
                "retry_attempt_failed",
                label=label,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(exc),
            )
            if attempt < max_attempts:
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    if last_exc is None:
        raise RuntimeError("retry() called with max_attempts < 1")
    raise last_exc
