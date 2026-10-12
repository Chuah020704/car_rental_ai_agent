"""JSON-backed ReservationRepository.

Mutations (save()) are written back to disk with an atomic replace so a crash
mid-write never corrupts the file — this is a toy "database" for a take-home,
but the write pattern is the same one you'd want for any file-backed store.
"""

import json
import os
import tempfile
from pathlib import Path

from app.enums import ReservationStatus
from app.models.schemas import Reservation
from app.utils.logging.logger import get_logger

logger = get_logger(__name__)


class JsonReservationRepository:
    """Implements the ReservationRepository protocol over a static JSON file."""

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._reservations = self._load()

    def _load(self) -> dict[str, Reservation]:
        raw = json.loads(self._data_path.read_text(encoding="utf-8"))
        reservations = {
            item["reservation_id"]: Reservation.model_validate(item) for item in raw
        }
        logger.info("reservation_repository_loaded", count=len(reservations))
        return reservations

    def get_by_id(self, reservation_id: str) -> Reservation | None:
        return self._reservations.get(reservation_id)

    def get_all(self) -> list[Reservation]:
        return list(self._reservations.values())

    def get_by_customer(self, customer_id: str) -> list[Reservation]:
        return [r for r in self._reservations.values() if r.customer_id == customer_id]

    def list_active_for_vehicle(
        self, vehicle_id: str, exclude_reservation_id: str | None = None
    ) -> list[Reservation]:
        return [
            r
            for r in self._reservations.values()
            if r.vehicle_id == vehicle_id
            and r.status == ReservationStatus.CONFIRMED
            and r.reservation_id != exclude_reservation_id
        ]

    def save(self, reservation: Reservation) -> None:
        self._reservations[reservation.reservation_id] = reservation
        self._persist()

    def _persist(self) -> None:
        payload = [r.model_dump(mode="json") for r in self._reservations.values()]
        fd, tmp_path = tempfile.mkstemp(
            dir=self._data_path.parent, prefix=".reservations_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp_path, self._data_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        logger.info("reservation_repository_persisted", path=str(self._data_path))
