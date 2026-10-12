"""Hybrid router node (Option C from planning).

Deterministic regex fast-path for the common, unambiguous cases — reservation
lookup and cancellation by ID both need nothing more than the ID itself to
build a complete tool call, so those are forced directly, skipping an LLM
round-trip entirely for that turn. Everything else (including "modify" intents,
whose arguments need natural-language date parsing a regex can't safely do)
defers to the ReAct agent's own tool-choice.
"""

import re
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.enums import RouteCategory, RouteSource
from app.models.schemas import RouteDecision
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)

_RESERVATION_ID_RE = re.compile(r"\b(R\d{3})\b", re.IGNORECASE)
_CANCEL_WORDS_RE = re.compile(r"\b(cancel|cancellation)\b", re.IGNORECASE)
_MODIFY_WORDS_RE = re.compile(r"\b(modify|change|reschedule|update)\b", re.IGNORECASE)

# Tools whose arguments a regex can safely build end-to-end (reservation_id only).
_FORCIBLE_TOOLS = {"get_reservation", "cancel_reservation"}


def resolve_route(message: str) -> tuple[RouteDecision, str | None]:
    """Return a routing decision plus the reservation ID extracted, if any."""
    match = _RESERVATION_ID_RE.search(message)
    reservation_id = match.group(1).upper() if match else None

    if reservation_id and _CANCEL_WORDS_RE.search(message):
        return (
            RouteDecision(
                category=RouteCategory.RESERVATION_MUTATION,
                tool="cancel_reservation",
                confidence=1.0,
                source=RouteSource.RULE,
            ),
            reservation_id,
        )

    if reservation_id and _MODIFY_WORDS_RE.search(message):
        # Category is known, but new dates need LLM extraction — not forcible.
        return (
            RouteDecision(
                category=RouteCategory.RESERVATION_MUTATION,
                tool="modify_reservation",
                confidence=0.6,
                source=RouteSource.REACT,
            ),
            reservation_id,
        )

    if reservation_id:
        return (
            RouteDecision(
                category=RouteCategory.RESERVATION_LOOKUP,
                tool="get_reservation",
                confidence=1.0,
                source=RouteSource.RULE,
            ),
            reservation_id,
        )

    return (
        RouteDecision(category=RouteCategory.GENERAL, tool=None, source=RouteSource.REACT),
        None,
    )


def route_node(state: AgentState) -> dict[str, Any]:
    """Graph node: compute the routing decision and, if forcible, inject the
    tool call directly into the message history."""
    last_message = state["messages"][-1]
    text = last_message.content if isinstance(last_message.content, str) else ""

    decision, reservation_id = resolve_route(text)
    logger.info(
        "route_decision",
        category=decision.category,
        tool=decision.tool,
        source=decision.source,
        confidence=decision.confidence,
    )

    if (
        decision.source == RouteSource.RULE
        and decision.tool in _FORCIBLE_TOOLS
        and reservation_id
    ):
        forced_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": decision.tool,
                    "args": {"reservation_id": reservation_id},
                    "id": str(uuid4()),
                    "type": "tool_call",
                }
            ],
        )
        return {
            "messages": [forced_message],
            "route_forced": True,
            "route_category": decision.category,
            "route_source": decision.source,
        }

    return {
        "route_forced": False,
        "route_category": decision.category,
        "route_source": decision.source,
    }


def route_after_router(state: AgentState) -> str:
    """Conditional edge: skip the agent/LLM node entirely when the router
    already forced a tool call."""
    return "tools" if state.get("route_forced") else "agent"
