"""JSON-backed VehicleRepository — loads data/vehicles.json once at construction."""

import json
from pathlib import Path

from app.models.schemas import Vehicle
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class JsonVehicleRepository:
    """Implements the VehicleRepository protocol over a static JSON file."""

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._vehicles = self._load()

    def _load(self) -> dict[str, Vehicle]:
        raw = json.loads(self._data_path.read_text(encoding="utf-8"))
        vehicles = {item["id"]: Vehicle.model_validate(item) for item in raw}
        logger.info("vehicle_repository_loaded", count=len(vehicles))
        return vehicles

    def get_all(self) -> list[Vehicle]:
        return list(self._vehicles.values())

    def get_by_id(self, vehicle_id: str) -> Vehicle | None:
        return self._vehicles.get(vehicle_id)
