"""Pydantic v2 domain models — the only data shape that crosses a function boundary.

No bare dicts: repositories return these models, services return these models,
tools serialize these models for the LLM. This is what "Pydantic v2 only for data
models; no bare dicts crossing a function boundary" in AGENTS.md means in practice.
"""

from datetime import date

from pydantic import BaseModel, Field

from app.enums import (
    PaymentStatus,
    ReservationStatus,
    RouteCategory,
    RouteSource,
    VehicleCategory,
)


class Vehicle(BaseModel):
    """A single rentable vehicle, as stored in data/vehicles.json."""

    id: str
    model: str
    category: VehicleCategory
    location: str
    price_per_day: float
    currency: str = "MYR"
    seats: int
    luggage: int
    transmission: str
    fuel_type: str
    available: bool = True
    features: list[str] = Field(default_factory=list)


class VehicleSearchCriteria(BaseModel):
    """Parsed arguments for the search_vehicles tool."""

    location: str
    pickup_date: date
    return_date: date
    passengers: int = 1
    luggage: int = 0
    category: VehicleCategory | None = None
    max_budget_per_day: float | None = None


class Reservation(BaseModel):
    """A single reservation, as stored in data/reservations.json."""

    reservation_id: str
    customer_id: str
    customer_name: str
    entra_upn: str | None = None
    vehicle_id: str
    pickup_date: date
    return_date: date
    pickup_location: str
    status: ReservationStatus
    payment_status: PaymentStatus
    insurance_purchased: bool
    total_price: float
    currency: str = "MYR"


class RouteDecision(BaseModel):
    """The Router Node's output — see app/agent/router.py (Phase 4)."""

    category: RouteCategory
    tool: str | None
    confidence: float | None = None
    source: RouteSource


class UsageMetadata(BaseModel):
    """Token accounting returned alongside LLM responses."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
