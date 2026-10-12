"""Vehicle search business rules, including date-overlap availability."""

from datetime import date

from app.enums import VehicleCategory
from app.models.schemas import VehicleSearchCriteria
from app.service.vehicle.vehicle_service import VehicleService


def test_search_filters_by_location_and_category(vehicle_service: VehicleService) -> None:
    criteria = VehicleSearchCriteria(
        location="Penang",
        pickup_date=date(2026, 10, 1),
        return_date=date(2026, 10, 3),
        passengers=4,
        category=VehicleCategory.SUV,
    )
    results = vehicle_service.search(criteria)
    assert all(v.location == "Penang" for v in results)
    assert all(v.category == VehicleCategory.SUV for v in results)


def test_search_excludes_vehicle_with_overlapping_reservation(
    vehicle_service: VehicleService,
) -> None:
    # R002 reserves V006 (Honda CR-V, KL) from 2026-10-12 to 2026-10-14.
    criteria = VehicleSearchCriteria(
        location="KL",
        pickup_date=date(2026, 10, 13),
        return_date=date(2026, 10, 16),
        passengers=2,
    )
    results = vehicle_service.search(criteria)
    assert all(v.id != "V006" for v in results)


def test_search_includes_vehicle_once_overlap_window_passes(
    vehicle_service: VehicleService,
) -> None:
    criteria = VehicleSearchCriteria(
        location="KL",
        pickup_date=date(2026, 10, 15),
        return_date=date(2026, 10, 17),
        passengers=2,
    )
    results = vehicle_service.search(criteria)
    assert any(v.id == "V006" for v in results)


def test_search_respects_budget_ceiling(vehicle_service: VehicleService) -> None:
    criteria = VehicleSearchCriteria(
        location="KL",
        pickup_date=date(2026, 12, 1),
        return_date=date(2026, 12, 3),
        passengers=1,
        max_budget_per_day=150,
    )
    results = vehicle_service.search(criteria)
    assert all(v.price_per_day <= 150 for v in results)


def test_search_excludes_unavailable_vehicle(vehicle_service: VehicleService) -> None:
    # V012 (Nissan Urvan, JB) is flagged available=false in the mock data.
    criteria = VehicleSearchCriteria(
        location="JB",
        pickup_date=date(2026, 12, 1),
        return_date=date(2026, 12, 3),
        passengers=10,
    )
    results = vehicle_service.search(criteria)
    assert all(v.id != "V012" for v in results)
