"""Router rule tests — pure function, no graph or LLM needed."""

from app.agent.router import resolve_route
from app.enums import RouteCategory, RouteSource


def test_reservation_lookup_is_forced_by_rule() -> None:
    decision, reservation_id = resolve_route("What is the status of my reservation R001?")
    assert decision.category == RouteCategory.RESERVATION_LOOKUP
    assert decision.tool == "get_reservation"
    assert decision.source == RouteSource.RULE
    assert reservation_id == "R001"


def test_cancel_with_id_is_forced_by_rule() -> None:
    decision, reservation_id = resolve_route("I want to cancel my booking R002")
    assert decision.category == RouteCategory.RESERVATION_MUTATION
    assert decision.tool == "cancel_reservation"
    assert decision.source == RouteSource.RULE
    assert reservation_id == "R002"


def test_modify_with_id_flags_category_but_defers_to_react() -> None:
    decision, reservation_id = resolve_route("Can I change my booking R006 to next week?")
    assert decision.category == RouteCategory.RESERVATION_MUTATION
    assert decision.source == RouteSource.REACT
    assert reservation_id == "R006"


def test_general_question_defers_to_react() -> None:
    decision, reservation_id = resolve_route(
        "I want to rent an SUV in Penang from 10 Oct to 15 Oct for 4 people"
    )
    assert decision.category == RouteCategory.GENERAL
    assert decision.tool is None
    assert decision.source == RouteSource.REACT
    assert reservation_id is None


def test_reservation_id_is_case_insensitive_and_uppercased() -> None:
    _decision, reservation_id = resolve_route("status of r003 please")
    assert reservation_id == "R003"
