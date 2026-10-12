"""Look up a customer's own reservation by ID.

`customer_id` is injected from graph state (InjectedState), never accepted as
an LLM-controllable argument — see AGENTS.md's security section. Ownership is
re-verified inside ReservationService regardless, so this guard holds even if
a future caller forgets to wire the injection correctly.
"""

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from app.agent.deps import get_reservation_service
from app.agent.tools._errors import safe_tool_error
from app.utils.exception.exceptions import AppException


class GetReservationArgs(BaseModel):
    reservation_id: str = Field(description="Reservation ID, e.g. R001")


@tool("get_reservation", args_schema=GetReservationArgs)
def get_reservation(
    reservation_id: str, state: Annotated[dict[str, Any], InjectedState]
) -> str:
    """Look up a reservation's status, vehicle, pickup/return info, payment
    status, and insurance. Use this whenever a customer asks about an existing
    booking by its reservation ID."""
    try:
        reservation = get_reservation_service().get_reservation(
            reservation_id, customer_id=state["customer_id"]
        )
    except AppException as exc:
        return safe_tool_error(exc)

    return (
        f"Reservation {reservation.reservation_id}: status={reservation.status}, "
        f"vehicle={reservation.vehicle_id}, pickup={reservation.pickup_date} "
        f"at {reservation.pickup_location}, return={reservation.return_date}, "
        f"payment={reservation.payment_status}, "
        f"insurance={'yes' if reservation.insurance_purchased else 'no'}, "
        f"total={reservation.total_price:.0f} {reservation.currency}"
    )
