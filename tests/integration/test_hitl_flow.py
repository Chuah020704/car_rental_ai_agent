"""Human-in-the-loop confirmation flow: interrupt() pauses before mutating,
Command(resume=...) continues only after explicit approval.

Uses an isolated copy of the mock data (never the committed data/ files, see
tests/conftest.py's isolated_mock_data fixture) and an in-memory SqliteSaver
checkpointer — this is the test that actually proves
cancel_reservation/modify_reservation can't mutate anything without a
confirmed Command(resume=...) round-trip.
"""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agent.graph import build_graph
from tests.fakes import ScriptedChatModel


def _reservation_status(data_dir: Path, reservation_id: str) -> str:
    reservations = json.loads((data_dir / "reservations.json").read_text())
    match = next(r for r in reservations if r["reservation_id"] == reservation_id)
    return str(match["status"])


def test_cancel_pauses_then_applies_only_after_approval(isolated_mock_data: Path) -> None:
    llm = ScriptedChatModel(responses=[AIMessage(content="Your reservation has been cancelled.")])

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_graph(llm, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "thread-cancel-1"}}

        result = graph.invoke(
            {
                "messages": [HumanMessage(content="I want to cancel my booking R002")],
                "customer_id": "C002",
                "customer_name": "Wei Jian Tan",
                "route_forced": False,
            },
            config=config,
        )

        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "confirm_cancel"
        assert payload["reservation_id"] == "R002"
        assert _reservation_status(isolated_mock_data, "R002") == "confirmed"

        result2 = graph.invoke(Command(resume={"approved": True}), config=config)

        assert result2["messages"][-1].content == "Your reservation has been cancelled."
        assert _reservation_status(isolated_mock_data, "R002") == "cancelled"


def test_cancel_declined_leaves_reservation_untouched(isolated_mock_data: Path) -> None:
    llm = ScriptedChatModel(responses=[AIMessage(content="Okay, no changes made.")])

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_graph(llm, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "thread-cancel-2"}}

        graph.invoke(
            {
                "messages": [HumanMessage(content="cancel R002")],
                "customer_id": "C002",
                "customer_name": "Wei Jian Tan",
                "route_forced": False,
            },
            config=config,
        )
        result = graph.invoke(Command(resume={"approved": False}), config=config)

        tool_message = result["messages"][-2]
        assert "not confirmed" in tool_message.content.lower()
        assert _reservation_status(isolated_mock_data, "R002") == "confirmed"


def test_cancel_already_cancelled_short_circuits_without_pausing(
    isolated_mock_data: Path,
) -> None:
    """R005 is already cancelled in the fixture data — the tool must say so
    immediately, never pausing to ask for confirmation on an action that's
    guaranteed to fail."""
    llm = ScriptedChatModel(
        responses=[AIMessage(content="That reservation is already cancelled.")]
    )

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_graph(llm, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "thread-cancel-3"}}

        result = graph.invoke(
            {
                "messages": [HumanMessage(content="Please cancel my reservation R005")],
                "customer_id": "C002",
                "customer_name": "Wei Jian Tan",
                "route_forced": False,
            },
            config=config,
        )

        assert "__interrupt__" not in result
        tool_message = result["messages"][-2]
        assert "already cancelled" in tool_message.content.lower()


def test_modify_pauses_then_applies_only_after_approval(isolated_mock_data: Path) -> None:
    tool_call_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "modify_reservation",
                "args": {
                    "reservation_id": "R006",
                    "new_pickup_date": "2026-10-21",
                    "new_return_date": "2026-10-24",
                },
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )
    final_message = AIMessage(content="Your dates have been updated.")
    llm = ScriptedChatModel(responses=[tool_call_message, final_message])

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_graph(llm, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "thread-modify-1"}}

        result = graph.invoke(
            {
                "messages": [HumanMessage(content="Can I move my booking R006 to Oct 21-24?")],
                "customer_id": "C004",
                "customer_name": "Siti Noraini",
                "route_forced": False,
            },
            config=config,
        )

        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "confirm_modify"

        result2 = graph.invoke(Command(resume={"approved": True}), config=config)

        assert result2["messages"][-1].content == "Your dates have been updated."
        reservations = json.loads(
            (isolated_mock_data / "reservations.json").read_text()
        )
        updated = next(r for r in reservations if r["reservation_id"] == "R006")
        assert updated["pickup_date"] == "2026-10-21"
        assert updated["total_price"] == pytest.approx(180 * 3)
