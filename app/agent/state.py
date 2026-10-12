"""LangGraph state schema — the single object threaded through every node."""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Graph state.

    `messages` uses LangGraph's `add_messages` reducer: nodes return a list of
    *new* messages to append, never the full history — the reducer merges them.
    `customer_id` is set once at invocation time from the verified JWT/Entra
    token (see app/api/dependencies in Phase 6) and never changes mid-run; tools
    read it via InjectedState rather than accepting it as an LLM argument.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    customer_id: str
    customer_name: str
    route_forced: bool
    route_category: str | None
    route_source: str | None
