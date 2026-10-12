"""Singletons the agent's tools depend on, built once per process.

Same lru_cache-singleton pattern as app.utils.config. FastAPI's dependency
injection (Phase 6) reuses these exact functions via Depends(...) — one
source of truth for "how do I get a ReservationService" whether you're inside
a LangGraph tool or a FastAPI route.
"""

from functools import lru_cache
from pathlib import Path

from app.repositories.reservation_repo import JsonReservationRepository
from app.repositories.vehicle_repo import JsonVehicleRepository
from app.service.reservation.reservation_service import ReservationService
from app.service.vehicle.vehicle_service import VehicleService

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache
def get_vehicle_repo() -> JsonVehicleRepository:
    return JsonVehicleRepository(_DATA_DIR / "vehicles.json")


@lru_cache
def get_reservation_repo() -> JsonReservationRepository:
    return JsonReservationRepository(_DATA_DIR / "reservations.json")


@lru_cache
def get_vehicle_service() -> VehicleService:
    return VehicleService(get_vehicle_repo(), get_reservation_repo())


@lru_cache
def get_reservation_service() -> ReservationService:
    return ReservationService(get_reservation_repo(), get_vehicle_repo())
