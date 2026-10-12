"""Repository interfaces (structural typing via typing.Protocol).

Services depend on these Protocols, not on the JSON-backed implementations
directly — swapping in a real REST-backed repository later means implementing
the same Protocol and changing one line in app/dependencies (Phase 6), with zero
changes to app/service/*.
"""

from typing import Protocol

from app.models.schemas import Reservation, Vehicle


class VehicleRepository(Protocol):
    def get_all(self) -> list[Vehicle]: ...

    def get_by_id(self, vehicle_id: str) -> Vehicle | None: ...


class ReservationRepository(Protocol):
    def get_all(self) -> list[Reservation]: ...

    def get_by_id(self, reservation_id: str) -> Reservation | None: ...

    def get_by_customer(self, customer_id: str) -> list[Reservation]: ...

    def list_active_for_vehicle(
        self, vehicle_id: str, exclude_reservation_id: str | None = None
    ) -> list[Reservation]: ...

    def save(self, reservation: Reservation) -> None: ...
