"""SSE event generation — in particular, the done-event-must-carry-thread_id
bug that would otherwise make a streaming client unable to learn a newly
minted thread_id when the first message of a conversation immediately pauses.
"""

import json

import pytest

from app.api.schemas import ChatResponse
from app.service.agent_runner import TraceEvent, TurnResult
from app.service.llm.streaming import stream_turn_result


@pytest.mark.asyncio
async def test_done_event_carries_thread_id_when_awaiting_confirmation() -> None:
    turn = TurnResult(
        response=ChatResponse(
            thread_id="t-123",
            status="awaiting_confirmation",
            confirmation={"type": "confirm_cancel", "reservation_id": "R002"},
        ),
        trace=[TraceEvent("confirmation_required", {"reservation_id": "R002"})],
    )

    events = [event async for event in stream_turn_result(turn)]

    done_event = next(e for e in events if e["event"] == "done")
    assert json.loads(done_event["data"]) == {
        "status": "awaiting_confirmation",
        "thread_id": "t-123",
    }


@pytest.mark.asyncio
async def test_done_event_carries_thread_id_on_ok_status() -> None:
    turn = TurnResult(
        response=ChatResponse(thread_id="t-456", status="ok", message="All set."),
        trace=[],
    )

    events = [event async for event in stream_turn_result(turn)]

    delta_event = next(e for e in events if e["event"] == "delta")
    assert json.loads(delta_event["data"]) == {"text": "All set."}
    done_event = next(e for e in events if e["event"] == "done")
    assert json.loads(done_event["data"]) == {"status": "ok", "thread_id": "t-456"}
