"""Cancel a reservation — pauses for explicit customer confirmation before
mutating anything.

interrupt() suspends graph execution at this exact point; the checkpointer
(see app/core/checkpoint.py) persists that paused state to disk, so the pause
survives across separate HTTP requests (and even a server restart). Execution
resumes only when the caller supplies Command(resume={"approved": ...}) — see
app/agent/graph.py and the /chat/confirm route in Phase 6.
"""

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agent.deps import get_reservation_service
from app.agent.tools._errors import safe_tool_error
from app.enums import ReservationStatus
from app.utils.exception.exceptions import AppException
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class CancelReservationArgs(BaseModel):
    reservation_id: str = Field(description="Reservation ID to cancel, e.g. R002")


@tool("cancel_reservation", args_schema=CancelReservationArgs)
def cancel_reservation(
    reservation_id: str, state: Annotated[dict[str, Any], InjectedState]
) -> str:
    """Cancel a reservation. ALWAYS pauses to ask the customer to confirm
    before cancelling — never completes without an explicit yes. Use this
    whenever a customer asks to cancel a booking."""
    service = get_reservation_service()
    try:
        reservation = service.get_reservation(reservation_id, customer_id=state["customer_id"])
    except AppException as exc:
        return safe_tool_error(exc)

    # Check mutability BEFORE interrupting — asking the customer to confirm
    # an action already guaranteed to fail (e.g. it's already cancelled) is
    # confusing busywork, not a real confirmation.
    if reservation.status != ReservationStatus.CONFIRMED:
        return f"Reservation {reservation_id} is already {reservation.status} and cannot be cancelled."

    fee = service.estimate_cancellation_fee(reservation)
    fee_note = (
        f"A cancellation fee of {fee:.0f} {reservation.currency} applies."
        if fee
        else "No cancellation fee applies."
    )
    summary = (
        f"Cancel reservation {reservation_id} (vehicle {reservation.vehicle_id}, "
        f"pickup {reservation.pickup_date})? {fee_note}"
    )

    decision = interrupt(
        {
            "type": "confirm_cancel",
            "reservation_id": reservation_id,
            "summary": summary,
            "cancellation_fee": fee,
        }
    )

    if not decision.get("approved"):
        logger.info("reservation_cancel_declined", reservation_id=reservation_id)
        return "No changes made — the cancellation was not confirmed."

    try:
        service.cancel_reservation(reservation_id, customer_id=state["customer_id"])
    except AppException as exc:
        return safe_tool_error(exc)

    return f"Reservation {reservation_id} has been cancelled."
