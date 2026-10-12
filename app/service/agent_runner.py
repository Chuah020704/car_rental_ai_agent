"""Core turn-runner shared by the JSON and SSE chat endpoints — exactly one
place that knows how to invoke the graph, mint thread_ids, and interpret
interrupts. Both app/api/routers/chat.py routes call this; neither re-derives
graph-invocation logic independently.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.api.schemas import ChatResponse


@dataclass
class TraceEvent:
    """One step of this turn's execution — replayed as an SSE event by
    app/service/llm/streaming.py."""

    type: str
    payload: dict[str, Any]


@dataclass
class TurnResult:
    response: ChatResponse
    trace: list[TraceEvent] = field(default_factory=list)


def run_turn(
    graph: CompiledStateGraph,
    *,
    message: str,
    thread_id: str | None,
    customer_id: str,
    customer_name: str,
) -> TurnResult:
    """Run one turn. Mints a thread_id if this is the first message in the
    conversation; otherwise only the new message is passed — the checkpointer
    already holds customer_id/customer_name/history from the prior turn, and
    LangGraph merges the partial update into that persisted state.
    """
    is_new_thread = thread_id is None
    resolved_thread_id = thread_id or str(uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": resolved_thread_id}}

    prior_count = 0
    if not is_new_thread:
        snapshot = graph.get_state(config)
        prior_count = len(snapshot.values.get("messages", []))

    if is_new_thread:
        result = graph.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "customer_id": customer_id,
                "customer_name": customer_name,
                "route_forced": False,
            },
            config=config,
        )
    else:
        result = graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)

    return _build_turn_result(result, resolved_thread_id, prior_count)


def run_confirm(graph: CompiledStateGraph, *, thread_id: str, approved: bool) -> TurnResult:
    """Resume a paused thread with the customer's confirm/decline decision."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    prior_count = len(snapshot.values.get("messages", []))

    result = graph.invoke(Command(resume={"approved": approved}), config=config)
    return _build_turn_result(result, thread_id, prior_count)


def _build_turn_result(
    result: dict[str, Any], thread_id: str, prior_count: int
) -> TurnResult:
    trace: list[TraceEvent] = []

    route_category = result.get("route_category")
    if route_category:
        trace.append(
            TraceEvent(
                "routing",
                {"category": route_category, "source": result.get("route_source")},
            )
        )

    new_messages: list[BaseMessage] = result["messages"][prior_count:]
    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                trace.append(TraceEvent("tool_call", {"tool": call["name"], "args": call["args"]}))
        elif isinstance(msg, ToolMessage):
            trace.append(TraceEvent("tool_result", {"tool": msg.name, "content": msg.content}))

    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        trace.append(TraceEvent("confirmation_required", payload))
        response = ChatResponse(
            thread_id=thread_id, status="awaiting_confirmation", confirmation=payload
        )
        return TurnResult(response=response, trace=trace)

    final_message = result["messages"][-1]
    response = ChatResponse(thread_id=thread_id, status="ok", message=final_message.content)
    return TurnResult(response=response, trace=trace)
