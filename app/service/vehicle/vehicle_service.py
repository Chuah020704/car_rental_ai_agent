"""Vehicle search business logic — pure functions over repositories, no LLM involved."""

from datetime import date

from app.models.schemas import Vehicle, VehicleSearchCriteria
from app.repositories.base import ReservationRepository, VehicleRepository


def _dates_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """Two date ranges overlap unless one ends before the other starts."""
    return a_start <= b_end and b_start <= a_end


class VehicleService:
    """Business rules for searching available vehicles."""

    def __init__(
        self, vehicle_repo: VehicleRepository, reservation_repo: ReservationRepository
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._reservation_repo = reservation_repo

    def search(self, criteria: VehicleSearchCriteria) -> list[Vehicle]:
        """Return vehicles matching location/category/budget/capacity and free
        for the requested date range (no overlapping confirmed reservation).
        """
        candidates = [
            v
            for v in self._vehicle_repo.get_all()
            if v.available
            and v.location.lower() == criteria.location.lower()
            and v.seats >= criteria.passengers
            and v.luggage >= criteria.luggage
            and (criteria.category is None or v.category == criteria.category)
            and (
                criteria.max_budget_per_day is None
                or v.price_per_day <= criteria.max_budget_per_day
            )
        ]
        return [v for v in candidates if self._is_free(v.id, criteria)]

    def _is_free(self, vehicle_id: str, criteria: VehicleSearchCriteria) -> bool:
        active = self._reservation_repo.list_active_for_vehicle(vehicle_id)
        return not any(
            _dates_overlap(
                criteria.pickup_date, criteria.return_date, r.pickup_date, r.return_date
            )
            for r in active
        )
