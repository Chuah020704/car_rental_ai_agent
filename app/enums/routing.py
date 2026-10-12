"""Router node enums — see app/agent/router.py (Phase 4)."""

from enum import StrEnum


class RouteSource(StrEnum):
    """Where a routing decision came from: a deterministic rule, or the ReAct
    agent's own tool-choice."""

    RULE = "rule"
    REACT = "react"


class RouteCategory(StrEnum):
    """High-level intent category a user message is routed to."""

    VEHICLE_SEARCH = "vehicle_search"
    RESERVATION_LOOKUP = "reservation_lookup"
    RESERVATION_MUTATION = "reservation_mutation"
    POLICY_QA = "policy_qa"
    GENERAL = "general"
