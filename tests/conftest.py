"""Shared pytest fixtures."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

import app.agent.deps as agent_deps
import app.dependencies.auth as auth_deps
from app.repositories.reservation_repo import JsonReservationRepository
from app.repositories.vehicle_repo import JsonVehicleRepository
from app.service.reservation.reservation_service import ReservationService
from app.service.vehicle.vehicle_service import VehicleService

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def vehicle_repo() -> JsonVehicleRepository:
    return JsonVehicleRepository(DATA_DIR / "vehicles.json")


@pytest.fixture
def reservation_repo(tmp_path: Path) -> JsonReservationRepository:
    """Mutation tests must never touch the committed data/reservations.json,
    so each test gets its own disposable copy."""
    tmp_reservations = tmp_path / "reservations.json"
    shutil.copy(DATA_DIR / "reservations.json", tmp_reservations)
    return JsonReservationRepository(tmp_reservations)


@pytest.fixture
def vehicle_service(
    vehicle_repo: JsonVehicleRepository, reservation_repo: JsonReservationRepository
) -> VehicleService:
    return VehicleService(vehicle_repo, reservation_repo)


@pytest.fixture
def reservation_service(
    reservation_repo: JsonReservationRepository, vehicle_repo: JsonVehicleRepository
) -> ReservationService:
    return ReservationService(reservation_repo, vehicle_repo)


@pytest.fixture
def isolated_mock_data(tmp_path: Path) -> Iterator[Path]:
    """Point the agent's singleton repos (and the auth layer's customer
    directory, which is derived from the same reservation data) at a
    disposable copy of the mock data for one test, then restore everything
    afterward. Needed by any test that runs the real graph/tools/API and
    might mutate a reservation — those must never touch the committed
    data/*.json files.
    """
    tmp_data_dir = tmp_path / "data"
    tmp_data_dir.mkdir()
    shutil.copy(DATA_DIR / "vehicles.json", tmp_data_dir / "vehicles.json")
    shutil.copy(DATA_DIR / "reservations.json", tmp_data_dir / "reservations.json")

    original_data_dir = agent_deps._DATA_DIR
    agent_deps._DATA_DIR = tmp_data_dir
    agent_deps.get_vehicle_repo.cache_clear()
    agent_deps.get_reservation_repo.cache_clear()
    agent_deps.get_vehicle_service.cache_clear()
    agent_deps.get_reservation_service.cache_clear()
    auth_deps.get_customer_directory.cache_clear()

    yield tmp_data_dir

    agent_deps._DATA_DIR = original_data_dir
    agent_deps.get_vehicle_repo.cache_clear()
    agent_deps.get_reservation_repo.cache_clear()
    agent_deps.get_vehicle_service.cache_clear()
    agent_deps.get_reservation_service.cache_clear()
    auth_deps.get_customer_directory.cache_clear()
