"""Modify a reservation's pickup/return dates — pauses for explicit customer
confirmation before mutating anything.

Scope is deliberately dates-only: vehicle or passenger-count changes are
rejected by ReservationService with guidance to cancel and rebook instead —
see docs/adr for why.
"""

from datetime import date
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


class ModifyReservationArgs(BaseModel):
    reservation_id: str = Field(description="Reservation ID to modify, e.g. R006")
    new_pickup_date: date = Field(description="New pickup date, YYYY-MM-DD")
    new_return_date: date = Field(description="New return date, YYYY-MM-DD")


@tool("modify_reservation", args_schema=ModifyReservationArgs)
def modify_reservation(
    reservation_id: str,
    new_pickup_date: date,
    new_return_date: date,
    state: Annotated[dict[str, Any], InjectedState],
) -> str:
    """Change a reservation's pickup and return dates. ALWAYS pauses to ask
    the customer to confirm the new dates before applying the change. Only
    dates can be changed — if a customer wants a different vehicle or
    passenger count, tell them to cancel and make a new booking instead."""
    service = get_reservation_service()
    try:
        reservation = service.get_reservation(reservation_id, customer_id=state["customer_id"])
    except AppException as exc:
        return safe_tool_error(exc)

    # Check mutability BEFORE interrupting — same reasoning as cancel_reservation.
    if reservation.status != ReservationStatus.CONFIRMED:
        return f"Reservation {reservation_id} is already {reservation.status} and cannot be modified."

    summary = (
        f"Change reservation {reservation_id} from {reservation.pickup_date} - "
        f"{reservation.return_date} to {new_pickup_date} - {new_return_date}?"
    )
    decision = interrupt(
        {
            "type": "confirm_modify",
            "reservation_id": reservation_id,
            "summary": summary,
            "new_pickup_date": str(new_pickup_date),
            "new_return_date": str(new_return_date),
        }
    )

    if not decision.get("approved"):
        logger.info("reservation_modify_declined", reservation_id=reservation_id)
        return "No changes made — the modification was not confirmed."

    try:
        updated = service.modify_reservation(
            reservation_id,
            customer_id=state["customer_id"],
            new_pickup_date=new_pickup_date,
            new_return_date=new_return_date,
        )
    except AppException as exc:
        return safe_tool_error(exc)

    return (
        f"Reservation {reservation_id} updated: {updated.pickup_date} to "
        f"{updated.return_date}, new total {updated.total_price:.0f} {updated.currency}."
    )
