"""Search for available vehicles by location, dates, passengers, luggage,
category, and budget."""

from datetime import date

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agent.deps import get_vehicle_service
from app.agent.tools._errors import safe_tool_error
from app.enums import VehicleCategory
from app.models.schemas import VehicleSearchCriteria
from app.utils.exception.exceptions import AppException


class SearchVehiclesArgs(BaseModel):
    """Arguments for search_vehicles — this schema IS the routing signal the
    LLM reads to decide when and how to call this tool."""

    location: str = Field(description="City: KL, Penang, JB, or Langkawi")
    pickup_date: date = Field(description="Pickup date, YYYY-MM-DD")
    return_date: date = Field(description="Return date, YYYY-MM-DD")
    passengers: int = Field(default=1, description="Number of passengers")
    luggage: int = Field(default=0, description="Number of luggage items")
    category: VehicleCategory | None = Field(
        default=None, description="economy, compact, suv, premium, or van"
    )
    max_budget_per_day: float | None = Field(
        default=None, description="Maximum price per day in MYR"
    )


@tool("search_vehicles", args_schema=SearchVehiclesArgs)
def search_vehicles(
    location: str,
    pickup_date: date,
    return_date: date,
    passengers: int = 1,
    luggage: int = 0,
    category: VehicleCategory | None = None,
    max_budget_per_day: float | None = None,
) -> str:
    """Search available vehicles by location, dates, passengers, luggage,
    category, and budget. Returns pricing for each match. Use this whenever a
    customer wants to rent, browse, or compare vehicles."""
    try:
        criteria = VehicleSearchCriteria(
            location=location,
            pickup_date=pickup_date,
            return_date=return_date,
            passengers=passengers,
            luggage=luggage,
            category=category,
            max_budget_per_day=max_budget_per_day,
        )
        results = get_vehicle_service().search(criteria)
    except AppException as exc:
        return safe_tool_error(exc)

    if not results:
        return "No vehicles are available matching that search."

    lines = [
        f"- {v.id}: {v.model} ({v.category}), {v.seats} seats, {v.luggage} luggage, "
        f"{v.price_per_day:.0f} {v.currency}/day"
        for v in results
    ]
    return "Available vehicles:\n" + "\n".join(lines)
