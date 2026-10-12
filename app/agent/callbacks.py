"""Logging callback handler — logs every tool call and its outcome.

Attached to the graph's run config so every agent invocation gets full
tool-call visibility in the structured logs, independent of the API layer;
Phase 6 reuses these same events to drive the SSE `tool_call`/`tool_result`
stream to the Streamlit UI.
"""

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class ToolCallLoggingHandler(BaseCallbackHandler):
    """Logs tool_start / tool_end / tool_error as structured events."""

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        logger.info(
            "tool_call_start",
            tool=serialized.get("name"),
            run_id=str(run_id),
            input=input_str,
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        logger.info("tool_call_end", run_id=str(run_id), output=str(output)[:500])

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        logger.error("tool_call_error", run_id=str(run_id), error=str(error))
