"""Test-only doubles — never imported by application code.

ScriptedChatModel stands in for a real provider when testing graph wiring: it
supports `bind_tools()` (as a no-op, matching the real interface) and returns a
pre-programmed sequence of AIMessages, so a full ReAct loop (including
tool-calling) can be exercised deterministically with zero network access or
API keys.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """Pops one pre-built AIMessage off `responses` per call, in order."""

    responses: list[AIMessage]
    _call_count: int = PrivateAttr(default=0)

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "ScriptedChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self.responses[self._call_count]
        self._call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"
